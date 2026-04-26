"""
sources/monitoring/monitoring.py
---------------------------------
Ongoing monitoring trigger for KYC Apexon.

Compares current fetch_state against a previous snapshot to identify
sources whose content has changed, then maps those sources to the
jurisdictions they cover (via registry.yaml) and returns the customer_ids
that should be re-evaluated.

Design constraints:
- No engine re-run — this module only identifies WHO needs re-evaluation.
- No writes — pure read + compare + report.
- Customers DataFrame is passed in by the caller (engine or dashboard).
- Source → jurisdiction mapping is read from registry.yaml via load_registry().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import logging
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SourceChange:
    """A single source whose state has changed since the last snapshot."""
    source_id: str
    jurisdiction: str          # from registry entry
    previous_hash: Optional[str]
    current_hash: Optional[str]
    previous_fetched_at: Optional[str]
    current_fetched_at: Optional[str]
    change_type: str           # "new_fetch" | "hash_changed" | "status_changed"


@dataclass
class MonitoringReport:
    """
    Output of MonitoringService.check().

    changed_sources  : sources whose content_hash or fetch timestamp changed.
    affected_jurisdictions : set of jurisdiction codes touched by changes.
    customer_ids_to_review : customer_ids (from the passed DataFrame) booked in
                             an affected jurisdiction.
    skipped_sources  : source_ids present in registry but missing from fetch_state.
    """
    changed_sources: List[SourceChange] = field(default_factory=list)
    affected_jurisdictions: Set[str] = field(default_factory=set)
    customer_ids_to_review: List[str] = field(default_factory=list)
    skipped_sources: List[str] = field(default_factory=list)

    @property
    def change_count(self) -> int:
        return len(self.changed_sources)

    @property
    def customer_count(self) -> int:
        return len(self.customer_ids_to_review)

    def summary(self) -> Dict:
        return {
            "change_count": self.change_count,
            "affected_jurisdictions": sorted(self.affected_jurisdictions),
            "customer_ids_to_review": self.customer_ids_to_review,
            "skipped_sources": self.skipped_sources,
        }


class MonitoringService:
    """
    Compares current fetch_state with a previous snapshot and identifies
    customers that need re-evaluation due to watchlist changes.

    Usage:
        service = MonitoringService()
        report = service.check(
            previous_snapshot=prev_state_dict,   # dict loaded from fetch_state.yaml
            customers_df=engine.customers,
        )
        # report.customer_ids_to_review → pass to engine.evaluate_customer()
    """

    def __init__(self):
        from sources.schema.registry import load_registry
        from sources.schema.fetch_state import load_fetch_state

        self._registry = load_registry()
        self._fetch_state = load_fetch_state()

        # Build source_id → jurisdiction lookup from registry
        self._source_jurisdiction: Dict[str, str] = {}
        for entry in self._registry.sources:
            for url_entry in entry.urls:
                self._source_jurisdiction[entry.id] = entry.jurisdiction
                break  # one jurisdiction per source

    def check(
        self,
        previous_snapshot: Dict,
        customers_df: pd.DataFrame,
    ) -> MonitoringReport:
        """
        Compare current fetch_state against previous_snapshot.

        Args:
            previous_snapshot: dict shaped like fetch_state.yaml —
                               keys are source_ids, values have
                               'content_hash' and 'last_fetched_at'.
            customers_df: DataFrame with at least 'customer_id' and
                          'jurisdiction' columns.

        Returns:
            MonitoringReport
        """
        report = MonitoringReport()

        current_state = self._fetch_state_as_dict()

        for source_id, current in current_state.items():
            prev = previous_snapshot.get(source_id)

            if prev is None:
                # Source not in previous snapshot — treat as new fetch
                change = SourceChange(
                    source_id=source_id,
                    jurisdiction=self._source_jurisdiction.get(source_id, "UNKNOWN"),
                    previous_hash=None,
                    current_hash=current.get("content_hash"),
                    previous_fetched_at=None,
                    current_fetched_at=current.get("last_fetched_at"),
                    change_type="new_fetch",
                )
                report.changed_sources.append(change)
                continue

            prev_hash = prev.get("content_hash")
            curr_hash = current.get("content_hash")
            prev_ts = prev.get("last_fetched_at")
            curr_ts = current.get("last_fetched_at")

            hash_changed = (
                curr_hash is not None
                and prev_hash is not None
                and curr_hash != prev_hash
            )
            ts_changed = curr_ts is not None and curr_ts != prev_ts

            if hash_changed:
                change_type = "hash_changed"
            elif ts_changed:
                change_type = "status_changed"
            else:
                continue  # no change

            change = SourceChange(
                source_id=source_id,
                jurisdiction=self._source_jurisdiction.get(source_id, "UNKNOWN"),
                previous_hash=prev_hash,
                current_hash=curr_hash,
                previous_fetched_at=prev_ts,
                current_fetched_at=curr_ts,
                change_type=change_type,
            )
            report.changed_sources.append(change)

        # Collect affected jurisdictions
        for change in report.changed_sources:
            if change.jurisdiction and change.jurisdiction != "UNKNOWN":
                report.affected_jurisdictions.add(change.jurisdiction.upper())

        # Map affected jurisdictions → customer_ids
        if (
            report.affected_jurisdictions
            and customers_df is not None
            and not customers_df.empty
            and "jurisdiction" in customers_df.columns
            and "customer_id" in customers_df.columns
        ):
            mask = customers_df["jurisdiction"].astype(str).str.upper().isin(
                report.affected_jurisdictions
            )
            report.customer_ids_to_review = (
                customers_df.loc[mask, "customer_id"].astype(str).tolist()
            )

        # Skipped: in registry but not in fetch_state
        current_ids = set(current_state.keys())
        for entry in self._registry.sources:
            if entry.id not in current_ids:
                report.skipped_sources.append(entry.id)

        logger.info(
            "MonitoringService.check(): %d changed sources, %d jurisdictions affected, "
            "%d customers flagged for re-evaluation",
            report.change_count,
            len(report.affected_jurisdictions),
            report.customer_count,
        )

        return report

    def snapshot(self) -> Dict:
        """
        Return the current fetch_state as a plain dict suitable for
        storing as a previous_snapshot for the next check() call.
        """
        return self._fetch_state_as_dict()

    def _fetch_state_as_dict(self) -> Dict:
        """Flatten fetch_state into {source_id: {content_hash, last_fetched_at}}."""
        result = {}
        for source_id, url_states in self._fetch_state.states.items():
            # url_states is a dict of url → UrlState
            latest_hash = None
            latest_ts = None
            for url_state in url_states.values():
                h = getattr(url_state, "last_hash", None)
                ts = getattr(url_state, "last_fetched_at", None)
                if ts and (latest_ts is None or str(ts) > str(latest_ts)):
                    latest_ts = str(ts) if ts else None
                    latest_hash = h
            result[source_id] = {
                "content_hash": latest_hash,
                "last_fetched_at": latest_ts,
            }
        return result
