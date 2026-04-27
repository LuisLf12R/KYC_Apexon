"""
Customer Decision Dashboard — Phase 11D.

Transforms raw engine batch results into a simplified decision view
for compliance officers.
"""

from typing import Any, Dict, List

import pandas as pd


_SCORE_FIELDS = [
    "overall_score",
    "aml_screening_score",
    "identity_verification_score",
    "account_activity_score",
    "proof_of_address_score",
    "beneficial_ownership_score",
    "data_quality_score",
    "source_of_wealth_score",
    "crs_fatca_score",
]


def _extract_rule_id(rule: Any) -> str:
    if isinstance(rule, dict):
        return str(rule.get("rule_id", rule.get("id", ""))).strip()
    if hasattr(rule, "rule_id"):
        return str(getattr(rule, "rule_id", "")).strip()
    return str(rule).strip()


def _collect_rule_ids(result: Dict[str, Any]) -> List[str]:
    rules: List[str] = []
    for key in ["triggered_rules", "triggered_reject_rules", "triggered_review_rules"]:
        for rule in result.get(key, []) or []:
            rid = _extract_rule_id(rule)
            if rid:
                rules.append(rid)
    return sorted(set(rules))


def _map_pass_or_reject(disposition: str) -> str:
    disp = str(disposition or "REVIEW").upper()
    if disp == "REJECT":
        return "REJECT"
    if disp == "REVIEW":
        return "REVIEW"
    return "PASS"


def _confidence_label(result: Dict[str, Any]) -> str:
    scores = []
    for field in _SCORE_FIELDS:
        value = result.get(field)
        if value is None:
            continue
        try:
            scores.append(float(value))
        except Exception:
            continue

    numeric = 0.0
    if scores:
        numeric = sum(scores) / len(scores)

    if numeric >= 80.0:
        level = "High"
    elif numeric >= 60.0:
        level = "Medium"
    else:
        level = "Low"
    return level + " (" + str(int(round(numeric))) + ")"


def _weakest_dimension(result: Dict[str, Any]) -> str:
    dim_scores = []
    for field in _SCORE_FIELDS:
        if not field.endswith("_score") or field == "overall_score":
            continue
        value = result.get(field)
        if value is None:
            continue
        try:
            dim_scores.append((field, float(value)))
        except Exception:
            continue
    if not dim_scores:
        return ""
    dim_scores.sort(key=lambda item: item[1])
    return dim_scores[0][0].replace("_score", "").replace("_", " ").title()


def _build_notes(result: Dict[str, Any], rule_ids: List[str]) -> str:
    disposition = str(result.get("disposition", "")).upper()
    weakest = _weakest_dimension(result)
    if rule_ids and disposition in ["REJECT", "REVIEW"]:
        return "Triggered: " + ", ".join(rule_ids[:3])
    if weakest:
        return "Weakest dimension: " + weakest
    rationale = str(result.get("rationale", "")).strip()
    if rationale:
        return rationale[:140]
    return "No material flags"


def build_decision_dashboard(batch_results: List[Dict[str, Any]]) -> pd.DataFrame:
    """Transform raw evaluate_batch results into a simplified decision dashboard."""
    columns = [
        "customer_id",
        "customer_name",
        "pass_or_reject",
        "confidence_level",
        "notes",
        "disposition",
        "triggered_rules",
    ]
    if not batch_results:
        return pd.DataFrame(columns=columns)

    rows: List[Dict[str, Any]] = []
    for result in batch_results:
        rid_list = _collect_rule_ids(result)
        disp = str(result.get("disposition", "REVIEW")).upper()
        rows.append(
            {
                "customer_id": result.get("customer_id", ""),
                "customer_name": result.get("customer_name", result.get("full_name", "")),
                "pass_or_reject": _map_pass_or_reject(disp),
                "confidence_level": _confidence_label(result),
                "notes": _build_notes(result, rid_list),
                "disposition": disp,
                "triggered_rules": rid_list,
            }
        )

    return pd.DataFrame(rows, columns=columns)
