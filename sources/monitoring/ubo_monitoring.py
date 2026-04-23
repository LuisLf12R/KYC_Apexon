"""
sources/monitoring/ubo_monitoring.py
UBO change-detection service for ongoing monitoring.

Compares current beneficial-ownership records against a previous snapshot
to identify customers whose UBO structure has changed and who therefore
need re-evaluation.

Change types detected:
- ubo_added       : new UBO record for a customer
- ubo_removed     : UBO record present in snapshot but missing now
- ownership_changed : ownership_pct changed for an existing UBO
- ubo_details_changed : name or other identifying field changed

Design constraints (same as MonitoringService):
- No engine re-run — identifies WHO needs re-evaluation only.
- No writes — pure compare + report.
- UBO DataFrame is passed in by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import logging
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class UBOChange:
    """A single UBO record change detected between snapshots."""
    customer_id: str
    owner_name: str
    change_type: str  # ubo_added | ubo_removed | ownership_changed | ubo_details_changed
    previous_value: Optional[str] = None
    current_value: Optional[str] = None


@dataclass
class UBOMonitoringReport:
    """Output of UBOMonitoringService.check()."""
    changes: List[UBOChange] = field(default_factory=list)
    affected_customer_ids: List[str] = field(default_factory=list)

    @property
    def change_count(self) -> int:
        return len(self.changes)

    @property
    def customer_count(self) -> int:
        return len(self.affected_customer_ids)

    def summary(self) -> Dict[str, Any]:
        return {
            "change_count": self.change_count,
            "affected_customer_ids": self.affected_customer_ids,
            "changes_by_type": self._changes_by_type(),
        }

    def _changes_by_type(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in self.changes:
            counts[c.change_type] = counts.get(c.change_type, 0) + 1
        return counts


class UBOMonitoringService:
    """
    Compares current UBO DataFrame against a previous snapshot to detect
    beneficial-ownership changes that require customer re-evaluation.

    Usage:
        service = UBOMonitoringService()
        snapshot = service.snapshot(ubo_df)
        # ... later ...
        report = service.check(previous_snapshot, current_ubo_df)
        # report.affected_customer_ids → pass to engine.evaluate_customer()
    """

    # Columns that identify a unique UBO record
    _KEY_COLS = ("customer_id", "owner_name")
    # Columns whose change triggers re-evaluation
    _WATCH_COLS = ("ownership_pct", "is_individual")

    def snapshot(self, ubo_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Capture the current UBO state as a serialisable list of dicts.

        Args:
            ubo_df: DataFrame with at least customer_id and owner_name columns.

        Returns:
            List of row dicts suitable for JSON serialisation and later
            comparison via check().
        """
        if ubo_df is None or ubo_df.empty:
            return []
        return ubo_df.to_dict(orient="records")

    def check(
        self,
        previous_snapshot: List[Dict[str, Any]],
        current_ubo_df: pd.DataFrame,
    ) -> UBOMonitoringReport:
        """
        Compare current UBO records against a previous snapshot.

        Args:
            previous_snapshot: output of a prior snapshot() call.
            current_ubo_df: current beneficial_ownership DataFrame.

        Returns:
            UBOMonitoringReport with changes and affected customer_ids.
        """
        report = UBOMonitoringReport()

        prev_df = pd.DataFrame(previous_snapshot) if previous_snapshot else pd.DataFrame()
        curr_df = current_ubo_df if current_ubo_df is not None else pd.DataFrame()

        # Normalise column presence
        for col in list(self._KEY_COLS) + list(self._WATCH_COLS):
            if not prev_df.empty and col not in prev_df.columns:
                prev_df[col] = ""
            if not curr_df.empty and col not in curr_df.columns:
                curr_df[col] = ""

        prev_keys = self._build_key_index(prev_df)
        curr_keys = self._build_key_index(curr_df)

        all_keys = set(prev_keys.keys()) | set(curr_keys.keys())
        affected: Set[str] = set()

        for key in all_keys:
            cid = key[0]
            owner = key[1] if len(key) > 1 else ""

            if key not in prev_keys:
                # New UBO
                report.changes.append(UBOChange(
                    customer_id=cid,
                    owner_name=owner,
                    change_type="ubo_added",
                    current_value=self._row_summary(curr_keys[key]),
                ))
                affected.add(cid)

            elif key not in curr_keys:
                # Removed UBO
                report.changes.append(UBOChange(
                    customer_id=cid,
                    owner_name=owner,
                    change_type="ubo_removed",
                    previous_value=self._row_summary(prev_keys[key]),
                ))
                affected.add(cid)

            else:
                # Both exist — check watched columns
                prev_row = prev_keys[key]
                curr_row = curr_keys[key]
                for col in self._WATCH_COLS:
                    pv = str(prev_row.get(col, "")).strip()
                    cv = str(curr_row.get(col, "")).strip()
                    if pv != cv:
                        report.changes.append(UBOChange(
                            customer_id=cid,
                            owner_name=owner,
                            change_type="ownership_changed" if col == "ownership_pct" else "ubo_details_changed",
                            previous_value=f"{col}={pv}",
                            current_value=f"{col}={cv}",
                        ))
                        affected.add(cid)

        report.affected_customer_ids = sorted(affected)

        logger.info(
            "UBOMonitoringService.check(): %d changes, %d customers affected",
            report.change_count,
            report.customer_count,
        )

        return report

    def _build_key_index(self, df: pd.DataFrame) -> Dict[tuple, Dict]:
        """Build (customer_id, owner_name) → row-dict index."""
        index: Dict[tuple, Dict] = {}
        if df.empty:
            return index
        for _, row in df.iterrows():
            cid = str(row.get("customer_id", "")).strip()
            owner = str(row.get("owner_name", "")).strip()
            key = (cid, owner)
            index[key] = row.to_dict()
        return index

    def _row_summary(self, row: Dict) -> str:
        """Short human-readable summary of a UBO row."""
        pct = row.get("ownership_pct", "?")
        return f"ownership_pct={pct}"
