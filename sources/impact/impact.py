"""
sources/impact/impact.py

Change-impact analysis for staged overlay proposals.

Given a proposed JurisdictionOverlay and a list of stored CustomerDecision
dicts, computes which decisions would change disposition under the new rules
WITHOUT re-running the full engine or re-fetching customer CSV data.

Methodology:
  Dimension scores are fixed — they depend on customer data, not ruleset params.
  Only the disposition layer (hard-reject rules, review rules, score thresholds)
  is re-evaluated against the proposed overlay. This is sound because:
    - Score threshold changes directly affect REVIEW-by-score cases.
    - New additional_hard_reject_rules / additional_review_rules change which
      dimension detail values trigger a new disposition.
    - Removed or loosened rules let previously-triggered cases through.

Usage (analyst workflow):
  1. Extractor produces rules/staging/GBR.json
  2. PR generator drafts PR_DRAFT.md
  3. Before merging, analyst calls compute_impact() against pending Review queue
  4. Flips are surfaced in dashboard — analyst decides whether to merge
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class ImpactFlip:
    """A single decision that would change disposition under the proposed overlay."""
    customer_id: str
    jurisdiction: str
    from_disposition: str
    to_disposition: str


@dataclass
class ImpactReport:
    """
    Full impact report for a proposed overlay against a set of decisions.

    Attributes
    ----------
    jurisdiction_code   : Jurisdiction the overlay targets.
    total_evaluated     : Number of decisions evaluated (filtered to jurisdiction).
    flips               : All decisions whose disposition would change.
    skipped             : Decisions skipped due to missing data (should be zero in production).
    """
    jurisdiction_code: str
    total_evaluated: int
    flips: List[ImpactFlip] = field(default_factory=list)
    skipped: int = 0

    @property
    def flip_count(self) -> int:
        return len(self.flips)

    def summary(self) -> Dict[str, Any]:
        """Human-readable summary dict for dashboard display."""
        from_counts: Dict[str, int] = {}
        to_counts: Dict[str, int] = {}
        for f in self.flips:
            from_counts[f.from_disposition] = from_counts.get(f.from_disposition, 0) + 1
            to_counts[f.to_disposition] = to_counts.get(f.to_disposition, 0) + 1
        return {
            "jurisdiction_code": self.jurisdiction_code,
            "total_evaluated": self.total_evaluated,
            "flip_count": self.flip_count,
            "skipped": self.skipped,
            "from_disposition_counts": from_counts,
            "to_disposition_counts": to_counts,
            "flips": [
                {
                    "customer_id": f.customer_id,
                    "from": f.from_disposition,
                    "to": f.to_disposition,
                }
                for f in self.flips
            ],
        }


# ── Disposition re-evaluation ──────────────────────────────────────────────────

def _matches_rule(rule: Dict[str, Any], dimension_results: Dict[str, Any]) -> bool:
    """
    Check whether a rule's condition matches the stored dimension detail values.
    Mirrors the logic in KYCComplianceEngine.determine_disposition().
    """
    dim = rule.get("dimension", "")
    field_name = rule.get("condition_field", "")
    value = rule.get("condition_value", "")
    details = dimension_results.get(f"{dim}_details", {})
    return str(details.get(field_name, "")).strip().lower() == str(value).strip().lower()


def compute_disposition_under_rules(
    decision: Dict[str, Any],
    hard_reject_rules: List[Dict[str, Any]],
    review_rules: List[Dict[str, Any]],
    score_thresholds: Dict[str, Any],
) -> str:
    """
    Re-evaluate disposition for a stored decision under a proposed rule set.

    Parameters
    ----------
    decision          : CustomerDecision-compatible dict (must have overall_score
                        and *_details fields).
    hard_reject_rules : Proposed combined hard-reject rules (baseline + overlay).
    review_rules      : Proposed combined review rules (baseline + overlay).
    score_thresholds  : Dict with pass_minimum and pass_with_notes_minimum.

    Returns
    -------
    Disposition string: "REJECT" | "REVIEW" | "PASS_WITH_NOTES" | "PASS"
    """
    score = float(decision.get("overall_score", 0))
    pass_min = int(score_thresholds.get("pass_minimum", 70))
    notes_min = int(score_thresholds.get("pass_with_notes_minimum", 50))

    # Hard reject takes absolute precedence
    for rule in hard_reject_rules:
        if _matches_rule(rule, decision):
            return "REJECT"

    # Review rules
    for rule in review_rules:
        if _matches_rule(rule, decision):
            return "REVIEW"

    # Score-based fallback (mirrors engine.determine_disposition logic)
    if score >= pass_min:
        return "PASS"
    elif score >= notes_min:
        return "PASS_WITH_NOTES"
    else:
        return "REVIEW"


# ── Main entrypoint ────────────────────────────────────────────────────────────

_LIVE_RULESET = Path("rules/kyc_rules_v2.0.json")


def compute_impact(
    jurisdiction_code: str,
    staged_overlay: Dict[str, Any],
    current_decisions: List[Dict[str, Any]],
    *,
    _ruleset_path: Path = _LIVE_RULESET,
) -> ImpactReport:
    """
    Compute which decisions would change disposition under a proposed overlay.

    Parameters
    ----------
    jurisdiction_code  : Code of the jurisdiction being changed, e.g. "GBR".
    staged_overlay     : JurisdictionOverlay-compatible dict (as read from
                         rules/staging/<CODE>.json).
    current_decisions  : List of CustomerDecision-compatible dicts. Only
                         decisions whose jurisdiction matches jurisdiction_code
                         are evaluated; others are ignored.
    _ruleset_path      : Override for testing.

    Returns
    -------
    ImpactReport
    """
    # Load live ruleset for baseline rules and thresholds
    if not _ruleset_path.exists():
        raise FileNotFoundError(f"Live ruleset not found at {_ruleset_path}")

    raw = json.loads(_ruleset_path.read_text(encoding="utf-8"))

    # Baseline rules
    baseline_hr = raw.get("hard_reject_rules", [])
    baseline_rv = raw.get("review_rules", [])
    score_thresholds = raw.get("score_thresholds", {"pass_minimum": 70, "pass_with_notes_minimum": 50})

    # Overlay additional rules — staged_overlay is a JurisdictionOverlay Pydantic model,
    # so use attribute access not .get()
    if hasattr(staged_overlay, "additional_hard_reject_rules"):
        additional_hr = staged_overlay.additional_hard_reject_rules or []
        additional_rv = staged_overlay.additional_review_rules or []
    else:
        additional_hr = staged_overlay.get("additional_hard_reject_rules", [])
        additional_rv = staged_overlay.get("additional_review_rules", [])

    proposed_hr = baseline_hr + additional_hr
    proposed_rv = baseline_rv + additional_rv

    # Filter decisions to this jurisdiction
    relevant = [
        d for d in current_decisions
        if str(d.get("jurisdiction", "")).strip() == jurisdiction_code
    ]

    flips: List[ImpactFlip] = []
    skipped = 0

    for decision in relevant:
        customer_id = decision.get("customer_id", "UNKNOWN")
        current_disposition = str(decision.get("disposition", "")).strip()

        if not current_disposition:
            skipped += 1
            continue

        try:
            proposed_disposition = compute_disposition_under_rules(
                decision,
                proposed_hr,
                proposed_rv,
                score_thresholds,
            )
        except Exception:
            skipped += 1
            continue

        if proposed_disposition != current_disposition:
            flips.append(
                ImpactFlip(
                    customer_id=customer_id,
                    jurisdiction=jurisdiction_code,
                    from_disposition=current_disposition,
                    to_disposition=proposed_disposition,
                )
            )

    return ImpactReport(
        jurisdiction_code=jurisdiction_code,
        total_evaluated=len(relevant),
        flips=flips,
        skipped=skipped,
    )
