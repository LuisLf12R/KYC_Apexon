"""
kyc_dashboard/tabs/dashboard.py
--------------------------------
KYC Operations dashboard — visual redesign aligned with the HNWI design system.
Design language: KPI strip · client worklist · case detail with flag-row dimensions.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from kyc_dashboard.components import (
    display_customer_name,
    get_configured_institution,
    mask,
    st_dataframe_safe,
)
from kyc_dashboard.tabs import audit_trail
from kyc_dashboard.tabs.individual import _get_available_institutions
from kyc_engine.ruleset import get_active_ruleset_version, reset_ruleset_cache
from rules.schema.ruleset import RulesetManifest


_RULESET_PATH = Path(__file__).resolve().parents[2] / "rules" / "kyc_rules_v2.0.json"

_SNAPSHOT_FIELDS = [
    "overall_score", "disposition",
    "aml_screening_score", "identity_verification_score",
    "account_activity_score", "proof_of_address_score",
    "beneficial_ownership_score", "data_quality_score",
    "source_of_wealth_score", "crs_fatca_score",
]

# ── Design-system CSS ──────────────────────────────────────────────────────────

_DASH_CSS = """
<style>
/* KYC HNWI design tokens — dark-mode adaptation */
.kyc-kpi-strip {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;
}
.kyc-kpi-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  padding: 18px 20px 14px;
}
.kyc-kpi-label {
  font-size: 11px; color: rgba(255,255,255,0.40);
  text-transform: uppercase; letter-spacing: 0.08em;
  font-weight: 500; margin-bottom: 6px;
}
.kyc-kpi-value {
  font-size: 30px; font-weight: 600; letter-spacing: -0.025em;
  color: #f3f4f7; line-height: 1; margin-bottom: 4px;
  font-variant-numeric: tabular-nums;
}
.kyc-kpi-sub { font-size: 12px; color: rgba(255,255,255,0.30); }
.kyc-kpi-delta {
  display: inline-flex; align-items: center;
  padding: 1px 6px; border-radius: 4px; font-size: 11px;
  font-weight: 500; margin-left: 6px; vertical-align: 3px;
}
.kyc-delta-ok   { color: oklch(72% 0.14 155); background: oklch(26% 0.06 155); }
.kyc-delta-bad  { color: oklch(72% 0.16 27);  background: oklch(28% 0.07 27); }
.kyc-delta-warn { color: oklch(80% 0.14 80);  background: oklch(28% 0.06 80); }

/* Badges */
.kyc-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 999px;
  font-size: 11.5px; font-weight: 500; white-space: nowrap;
}
.kyc-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.kyc-b-ok     { color: oklch(72% 0.14 155); background: oklch(26% 0.06 155); }
.kyc-b-warn   { color: oklch(80% 0.14 80);  background: oklch(28% 0.06 80); }
.kyc-b-bad    { color: oklch(72% 0.16 27);  background: oklch(28% 0.07 27); }
.kyc-b-mute   { color: rgba(255,255,255,0.50); background: rgba(255,255,255,0.07); }
.kyc-b-accent { color: oklch(72% 0.16 265); background: oklch(28% 0.08 265); }

/* Card */
.kyc-card {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  background: rgba(255,255,255,0.02);
  overflow: hidden;
  margin-bottom: 14px;
}
.kyc-card-h {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.85);
}
.kyc-card-h .meta { font-size: 12px; font-weight: 400; color: rgba(255,255,255,0.35); }

/* Client avatar */
.kyc-ini {
  width: 30px; height: 30px; border-radius: 50%;
  background: rgba(255,255,255,0.09); color: rgba(255,255,255,0.65);
  display: inline-grid; place-items: center;
  font-size: 11px; font-weight: 600; flex: 0 0 auto;
}

/* Risk bar (5 bars) */
.kyc-riskbar { display: inline-flex; align-items: flex-end; gap: 2px; vertical-align: middle; }
.kyc-riskbar span { width: 4px; border-radius: 1.5px; display: block; }

/* Client list rows (visual only — interaction via selectbox) */
.kyc-tbl-h {
  display: grid; grid-template-columns: 1fr 90px 100px;
  padding: 7px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.02);
  font-size: 10.5px; font-weight: 500; color: rgba(255,255,255,0.35);
  text-transform: uppercase; letter-spacing: 0.06em;
}
.kyc-row {
  display: grid; grid-template-columns: 1fr 90px 100px;
  align-items: center; padding: 10px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  font-size: 13px;
}
.kyc-row:last-child { border-bottom: 0; }
.kyc-row.kyc-selected { background: oklch(24% 0.07 265); }
.kyc-row-client { display: flex; align-items: center; gap: 10px; min-width: 0; }
.kyc-row-name { font-weight: 500; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kyc-row-meta { font-size: 11.5px; color: rgba(255,255,255,0.40); margin-top: 1px; }
.kyc-row-risk { display: flex; align-items: center; gap: 6px; }
.kyc-score-num { font-size: 12px; font-variant-numeric: tabular-nums; color: rgba(255,255,255,0.55); }
.kyc-row-badge { text-align: right; }

/* Section header */
.kyc-section-h {
  display: flex; align-items: center; justify-content: space-between;
  margin: 16px 0 10px;
}
.kyc-section-h h3 { margin: 0; font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.85); }
.kyc-section-h .meta { font-size: 12px; color: rgba(255,255,255,0.35); }

/* Flag rows (KYC dimension status, triggered rules) */
.kyc-flags { }
.kyc-flag-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 18px; border-top: 1px solid rgba(255,255,255,0.05);
  font-size: 13px;
}
.kyc-flag-row:first-child { border-top: 0; }
.kyc-flag-left { display: flex; align-items: center; gap: 12px; }
.kyc-flag-ico {
  width: 28px; height: 28px; border-radius: 7px;
  background: rgba(255,255,255,0.06);
  display: inline-grid; place-items: center;
  font-size: 13px; flex: 0 0 auto;
}
.kyc-flag-ico-ok   { background: oklch(26% 0.06 155); color: oklch(72% 0.14 155); }
.kyc-flag-ico-warn { background: oklch(28% 0.06 80);  color: oklch(80% 0.14 80); }
.kyc-flag-ico-bad  { background: oklch(28% 0.07 27);  color: oklch(72% 0.16 27); }
.kyc-flag-title { font-size: 13px; font-weight: 500; color: rgba(255,255,255,0.85); }
.kyc-flag-sub { font-size: 11.5px; color: rgba(255,255,255,0.40); margin-top: 1px; }

/* Customer header in detail panel */
.kyc-detail-hdr {
  padding: 14px 0 12px;
}
.kyc-detail-name {
  font-size: 20px; font-weight: 600; letter-spacing: -0.02em;
  color: #f3f4f7; margin-bottom: 4px;
}
.kyc-detail-meta {
  font-size: 12.5px; color: rgba(255,255,255,0.45);
}

/* 3-KPI mini strip for detail panel */
.kyc-mini-strip {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0;
}
.kyc-mini-card {
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07);
  border-radius: 10px; padding: 12px 14px;
  text-align: center;
}
.kyc-mini-label { font-size: 10px; color: rgba(255,255,255,0.35); text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 5px; }
.kyc-mini-value { font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1; }
</style>
"""


# ── Utility helpers ────────────────────────────────────────────────────────────

def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _as_float(value: Any) -> float:
    try:
        if value is None or pd.isna(value):
            return 0.0
    except Exception:
        if value is None:
            return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def _first_present(mapping: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _safe_str(mapping.get(key))
        if value:
            return value
    return ""


def _get_customer_row(customers_df: Optional[pd.DataFrame], customer_id: str) -> Dict[str, Any]:
    if customers_df is None or customers_df.empty or "customer_id" not in customers_df.columns:
        return {}
    rows = customers_df[customers_df["customer_id"].astype(str) == str(customer_id)]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def _get_related_row(df: Optional[pd.DataFrame], customer_id: str) -> Dict[str, Any]:
    if df is None or df.empty or "customer_id" not in df.columns:
        return {}
    rows = df[df["customer_id"].astype(str) == str(customer_id)]
    if rows.empty:
        return {}
    sort_col = None
    for candidate in ["verification_date", "issue_date", "screening_date", "last_txn_date", "transaction_date"]:
        if candidate in rows.columns:
            sort_col = candidate
            break
    if sort_col:
        try:
            rows = rows.assign(_sort_key=pd.to_datetime(rows[sort_col], errors="coerce")).sort_values(
                "_sort_key", ascending=False, na_position="last"
            )
            return rows.iloc[0].drop(labels=["_sort_key"]).to_dict()
        except Exception:
            pass
    return rows.iloc[0].to_dict()


def _confidence_score(result: Dict[str, Any]) -> int:
    return int(round(max(0.0, min(100.0, _as_float(result.get("overall_score"))))))


def _risk_level(score: int) -> int:
    """Map 0-100 score to 1-5 risk level (inverted — lower score = higher risk)."""
    if score >= 85:
        return 1
    if score >= 70:
        return 2
    if score >= 55:
        return 3
    if score >= 40:
        return 4
    return 5


def _risk_color(level: int) -> str:
    return {1: "oklch(72% 0.14 155)", 2: "oklch(72% 0.14 155)",
            3: "oklch(80% 0.14 80)", 4: "oklch(72% 0.16 27)", 5: "oklch(72% 0.16 27)"}.get(level, "gray")


def _score_color(score: float) -> str:
    if score >= 70:
        return "oklch(72% 0.14 155)"
    if score >= 50:
        return "oklch(80% 0.14 80)"
    return "oklch(72% 0.16 27)"


def _risk_bar_html(score: int) -> str:
    level = _risk_level(score)
    color = _risk_color(level)
    bars = ""
    for i in range(1, 6):
        h = 6 + i * 2
        bg = color if i <= level else "rgba(255,255,255,0.10)"
        bars += f"<span style='height:{h}px;background:{bg}'></span>"
    return f"<span class='kyc-riskbar'>{bars}</span>"


def _badge_html(text: str, tone: str) -> str:
    cls = {"ok": "kyc-b-ok", "warn": "kyc-b-warn", "bad": "kyc-b-bad",
           "mute": "kyc-b-mute", "accent": "kyc-b-accent"}.get(tone, "kyc-b-mute")
    return f"<span class='kyc-badge {cls}'><span class='kyc-dot'></span>{text}</span>"


def _ini_html(name: str) -> str:
    parts = name.upper().split()
    ini = (parts[0][0] + parts[-1][0]) if len(parts) >= 2 else name[:2].upper()
    return f"<span class='kyc-ini'>{ini}</span>"


def _disposition_tone(disposition: str) -> str:
    d = str(disposition).upper()
    if d == "PASS":
        return "ok"
    if d == "PASS_WITH_NOTES":
        return "warn"
    if d == "REVIEW":
        return "warn"
    return "bad"


def _extract_rule_ids(result: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for key in ["triggered_rules", "triggered_reject_rules", "triggered_review_rules"]:
        for item in result.get(key, []) or []:
            if isinstance(item, dict):
                rule_id = _safe_str(item.get("rule_id") or item.get("id"))
            else:
                rule_id = _safe_str(getattr(item, "rule_id", "")) or _safe_str(item)
            if rule_id:
                ids.append(rule_id)
    return sorted(set(ids))


def _decision_label(disposition: str) -> str:
    if str(disposition or "").upper() in ("PASS", "PASS_WITH_NOTES"):
        return "PASS"
    return "FAIL"


def _entity_label(value: str) -> str:
    cleaned = _safe_str(value).upper()
    if not cleaned:
        return "Unknown"
    if any(t in cleaned for t in ["LEGAL", "CORP", "COMPANY", "ENTITY"]):
        return "Corporate"
    if "INDIVIDUAL" in cleaned:
        return "Individual"
    return cleaned.title()


def _weakest_dimension(result: Dict[str, Any]) -> str:
    dims = []
    for field in ["aml_screening_score", "identity_verification_score",
                  "account_activity_score", "proof_of_address_score",
                  "beneficial_ownership_score", "data_quality_score",
                  "source_of_wealth_score", "crs_fatca_score"]:
        dims.append((field, _as_float(result.get(field))))
    dims = [d for d in dims if d[1] > 0]
    if not dims:
        return ""
    dims.sort(key=lambda x: x[1])
    return dims[0][0].replace("_score", "").replace("_", " ").title()


def _build_flags(result: Dict[str, Any], rule_ids: List[str]) -> List[str]:
    flags: List[str] = []
    if _safe_str(result.get("rationale")) or rule_ids:
        flags.append("Note")
    if _as_float(result.get("beneficial_ownership_score", 0)) < 70 and _as_float(result.get("beneficial_ownership_score", 0)) > 0:
        flags.append("UBO")
    if any(_as_float(result.get(f, 0)) < 70 and _as_float(result.get(f, 0)) > 0
           for f in ["identity_verification_score", "proof_of_address_score"]):
        flags.append("Doc")
    return flags


def _format_date(value: Any) -> str:
    if value is None or _safe_str(value) == "":
        return "-"
    try:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return _safe_str(value)
        return dt.strftime("%d %b %Y")
    except Exception:
        return _safe_str(value)


def _result_lookup(batch_results: pd.DataFrame, customer_id: str) -> Dict[str, Any]:
    if batch_results is None or batch_results.empty:
        return {}
    rows = batch_results[batch_results["customer_id"].astype(str) == str(customer_id)]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


# ── HTML component builders ────────────────────────────────────────────────────

def _kpi_strip_html(queue_df: pd.DataFrame) -> str:
    total = len(queue_df)
    pass_count  = int((queue_df["decision"] == "PASS").sum()) if total else 0
    fail_count  = int((queue_df["decision"] == "FAIL").sum()) if total else 0
    review_count = int(queue_df["disposition"].isin(["REJECT", "REVIEW"]).sum()) if total else 0
    avg_score   = round(queue_df["confidence_score"].mean(), 1) if total else 0.0
    pass_rate   = int(round(pass_count / total * 100)) if total else 0
    fail_tone_cls = "kyc-delta-bad" if fail_count > 0 else "kyc-delta-ok"

    cards = [
        {
            "label": "Customers evaluated",
            "value": str(total),
            "sub":   "in current queue run",
            "delta": None,
        },
        {
            "label": "Pass rate",
            "value": f"{pass_rate}%",
            "sub":   f"{pass_count} customers cleared",
            "delta": None,
        },
        {
            "label": "Require review",
            "value": str(review_count),
            "sub":   "REJECT or REVIEW disposition",
            "delta": (fail_tone_cls, str(fail_count) + " hard fail") if fail_count > 0 else None,
        },
        {
            "label": "Avg. confidence",
            "value": f"{avg_score}",
            "sub":   "out of 100",
            "delta": None,
        },
    ]

    html = "<div class='kyc-kpi-strip'>"
    for c in cards:
        delta_html = ""
        if c["delta"]:
            delta_html = f"<span class='kyc-kpi-delta {c['delta'][0]}'>{c['delta'][1]}</span>"
        html += (
            f"<div class='kyc-kpi-card'>"
            f"<div class='kyc-kpi-label'>{c['label']}</div>"
            f"<div class='kyc-kpi-value'>{c['value']}{delta_html}</div>"
            f"<div class='kyc-kpi-sub'>{c['sub']}</div>"
            f"</div>"
        )
    html += "</div>"
    return html


def _client_list_html(rows: List[Dict[str, Any]], selected_id: str) -> str:
    html = (
        "<div class='kyc-card'>"
        "<div class='kyc-card-h'>"
        "<span>Active queue</span>"
        f"<span class='meta'>{len(rows)} customers</span>"
        "</div>"
        "<div class='kyc-tbl-h'>"
        "<div>Client</div><div>Risk</div><div style='text-align:right'>Status</div>"
        "</div>"
        "<div class='kyc-flags'>"
    )
    for r in rows:
        sel_cls = "kyc-selected" if r["customer_id"] == selected_id else ""
        ini = _ini_html(r.get("customer_name_raw") or r["customer_id"])
        score = r["confidence_score"]
        risk_bar = _risk_bar_html(score)
        tone = _disposition_tone(r.get("disposition", "REVIEW"))
        label = r.get("disposition", "REVIEW").replace("_", " ").title()
        badge = _badge_html(label, tone)
        meta = f"{r.get('entity_type','')}"
        if r.get("jurisdiction"):
            meta += f" · {r['jurisdiction']}"
        html += (
            f"<div class='kyc-row {sel_cls}'>"
            f"<div class='kyc-row-client'>{ini}"
            f"<div><div class='kyc-row-name'>{r['customer_name_display']}</div>"
            f"<div class='kyc-row-meta'>{meta}</div></div></div>"
            f"<div class='kyc-row-risk'>{risk_bar}"
            f"<span class='kyc-score-num'>{score}</span></div>"
            f"<div class='kyc-row-badge'>{badge}</div>"
            "</div>"
        )
    html += "</div></div>"
    return html


def _needs_attention_html(result: Dict[str, Any]) -> str:
    """Flag rows for triggered reject/review rules."""
    reject_rules = result.get("triggered_reject_rules") or []
    review_rules = result.get("triggered_review_rules") or []

    if not reject_rules and not review_rules:
        return ""

    rows_html = ""
    for r in reject_rules:
        name = _safe_str(r.get("name") or r.get("rule_id", ""))
        desc = _safe_str(r.get("description", ""))[:90]
        rows_html += (
            "<div class='kyc-flag-row'>"
            "<div class='kyc-flag-left'>"
            "<div class='kyc-flag-ico kyc-flag-ico-bad'>✕</div>"
            "<div>"
            f"<div class='kyc-flag-title'>{name}</div>"
            f"<div class='kyc-flag-sub'>{desc}</div>"
            "</div></div>"
            f"<span class='kyc-badge kyc-b-bad'><span class='kyc-dot'></span>Hard Reject</span>"
            "</div>"
        )
    for r in review_rules:
        name = _safe_str(r.get("name") or r.get("rule_id", ""))
        desc = _safe_str(r.get("description", ""))[:90]
        rows_html += (
            "<div class='kyc-flag-row'>"
            "<div class='kyc-flag-left'>"
            "<div class='kyc-flag-ico kyc-flag-ico-warn'>⚑</div>"
            "<div>"
            f"<div class='kyc-flag-title'>{name}</div>"
            f"<div class='kyc-flag-sub'>{desc}</div>"
            "</div></div>"
            f"<span class='kyc-badge kyc-b-warn'><span class='kyc-dot'></span>Review</span>"
            "</div>"
        )

    return (
        "<div class='kyc-section-h'>"
        "<h3>What needs attention</h3>"
        f"<span class='meta'>{len(reject_rules) + len(review_rules)} triggered</span>"
        "</div>"
        f"<div class='kyc-card'><div class='kyc-flags'>{rows_html}</div></div>"
    )


def _dimension_flags_html(result: Dict[str, Any]) -> str:
    """KYC dimension status as design-system flag rows."""
    dim_fields = [
        ("AML Screening",         "aml_screening_score",         "aml_screening_details"),
        ("Identity Verification", "identity_verification_score", "identity_verification_details"),
        ("Account Activity",      "account_activity_score",      "account_activity_details"),
        ("Proof of Address",      "proof_of_address_score",      "proof_of_address_details"),
        ("Beneficial Ownership",  "beneficial_ownership_score",  "beneficial_ownership_details"),
        ("Data Quality",          "data_quality_score",          "data_quality_details"),
        ("Source of Wealth",      "source_of_wealth_score",      "source_of_wealth_details"),
        ("CRS / FATCA",           "crs_fatca_score",             "crs_fatca_details"),
    ]

    rows_html = ""
    any_shown = False
    for label, score_field, details_field in dim_fields:
        s = _as_float(result.get(score_field))
        if s == 0:
            continue
        any_shown = True
        finding = _safe_str(
            (result.get(details_field) or {}).get("finding", "") if isinstance(result.get(details_field), dict) else ""
        )
        if not finding:
            finding = f"Score: {int(s)}/100"

        if s >= 70:
            ico_cls, ico_char, badge_tone, badge_lbl = "kyc-flag-ico-ok", "✓", "ok", "Pass"
        elif s >= 50:
            ico_cls, ico_char, badge_tone, badge_lbl = "kyc-flag-ico-warn", "⚑", "warn", "Attention"
        else:
            ico_cls, ico_char, badge_tone, badge_lbl = "kyc-flag-ico-bad", "✕", "bad", "Fail"

        rows_html += (
            "<div class='kyc-flag-row'>"
            "<div class='kyc-flag-left'>"
            f"<div class='kyc-flag-ico {ico_cls}'>{ico_char}</div>"
            "<div>"
            f"<div class='kyc-flag-title'>{label}</div>"
            f"<div class='kyc-flag-sub'>{finding[:100]}</div>"
            "</div></div>"
            f"<span class='kyc-badge kyc-b-{badge_tone}'>"
            f"<span class='kyc-dot'></span>{badge_lbl} · {int(s)}</span>"
            "</div>"
        )

    if not any_shown:
        return ""

    return (
        "<div class='kyc-section-h'><h3>KYC dimensions</h3>"
        "<span class='meta'>click a dimension to drill in</span></div>"
        f"<div class='kyc-card'><div class='kyc-flags'>{rows_html}</div></div>"
    )


def _detail_header_html(queue_row: Dict[str, Any]) -> str:
    score = queue_row["confidence_score"]
    disposition = queue_row.get("disposition", "REVIEW")
    tone = _disposition_tone(disposition)
    disp_label = disposition.replace("_", " ").title()
    risk_level = _risk_level(score)
    risk_labels = {1: "Very Low", 2: "Low", 3: "Medium", 4: "High", 5: "Very High"}
    risk_col = _risk_color(risk_level)
    n_flags = queue_row.get("flag_count", 0)
    flag_col = "oklch(72% 0.16 27)" if n_flags > 0 else "rgba(255,255,255,0.40)"

    return (
        f"<div class='kyc-detail-hdr'>"
        f"<div class='kyc-detail-name'>{queue_row['customer_name_display']}</div>"
        f"<div class='kyc-detail-meta'>"
        f"{queue_row['customer_id']} · {queue_row.get('entity_type','')} · {queue_row.get('jurisdiction','')}"
        f"</div></div>"
        f"<div class='kyc-mini-strip'>"
        f"<div class='kyc-mini-card'>"
        f"<div class='kyc-mini-label'>Confidence</div>"
        f"<div class='kyc-mini-value' style='color:{_score_color(score)}'>{score}</div>"
        f"</div>"
        f"<div class='kyc-mini-card'>"
        f"<div class='kyc-mini-label'>Risk</div>"
        f"<div class='kyc-mini-value' style='color:{risk_col}'>{risk_labels[risk_level]}</div>"
        f"</div>"
        f"<div class='kyc-mini-card'>"
        f"<div class='kyc-mini-label'>Flags</div>"
        f"<div class='kyc-mini-value' style='color:{flag_col}'>{n_flags}</div>"
        f"</div>"
        f"</div>"
        f"<div style='margin-bottom:12px'>{_badge_html(disp_label, tone)}"
        f"&nbsp;<span style='font-size:12px;color:rgba(255,255,255,0.40)'>"
        f"{queue_row.get('notes','')[:100]}</span></div>"
    )


# ── Queue batch runner ─────────────────────────────────────────────────────────

def _run_dashboard_batch(user: Dict[str, Any], logger: Any, institution_id: Optional[str]) -> None:
    customers_df = st.session_state.get("customers_df")
    if customers_df is None or customers_df.empty:
        st.warning("Load customer data in Data & Documents before running the queue.")
        return

    customer_ids = customers_df["customer_id"].astype(str).tolist()
    batch_id = str(uuid.uuid4())[:8].upper()
    if logger:
        logger.log("BATCH_RUN_START", batch_id=batch_id,
                   details={"total": len(customer_ids), "initiated_by": user["username"],
                            "institution_id": institution_id})

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    progress = st.progress(0.0)
    status_ph = st.empty()

    for idx, customer_id in enumerate(customer_ids):
        try:
            result = st.session_state.kyc_engine.evaluate_customer(customer_id, institution_id=institution_id)
            if "ruleset_version" not in result:
                result["ruleset_version"] = get_active_ruleset_version()
            results.append(result)
        except Exception as exc:
            errors.append({"id": customer_id, "error": str(exc)})
        progress.progress((idx + 1) / max(len(customer_ids), 1))
        status_ph.text(f"{idx + 1}/{len(customer_ids)}")

    progress.empty()
    status_ph.empty()

    rdf = pd.DataFrame(results) if results else pd.DataFrame(
        columns=["customer_id", "overall_score", "disposition", "rationale", "ruleset_version"]
    )

    for col, default in [("disposition", "REVIEW"), ("overall_score", 0), ("rationale", ""), ("ruleset_version", get_active_ruleset_version())]:
        if col not in rdf.columns:
            rdf[col] = default

    for field in [c for c in rdf.columns if c.endswith("_score")]:
        rdf[field] = pd.to_numeric(rdf[field], errors="coerce").fillna(0.0)
    rdf["disposition"] = rdf["disposition"].fillna("REVIEW")

    order = {"REJECT": 0, "REVIEW": 1, "PASS_WITH_NOTES": 2, "PASS": 3}
    rdf["_sort"] = rdf["disposition"].map(order).fillna(4)
    rdf = rdf.sort_values(["_sort", "overall_score"]).drop(columns=["_sort"])

    st.session_state.batch_results = rdf
    st.session_state.batch_id = batch_id
    st.session_state.batch_run_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if not rdf.empty:
        st.session_state.dashboard_selected_customer_id = _safe_str(rdf.iloc[0]["customer_id"])

    if logger:
        reject_count = int((rdf["disposition"] == "REJECT").sum()) if "disposition" in rdf.columns else 0
        review_count = int((rdf["disposition"] == "REVIEW").sum()) if "disposition" in rdf.columns else 0
        logger.log("BATCH_RUN_COMPLETE", batch_id=batch_id,
                   details={"evaluated": len(results), "errors": len(errors),
                            "reject": reject_count, "review": review_count,
                            "avg_score": float(rdf["overall_score"].mean()) if "overall_score" in rdf.columns and len(rdf) else 0.0})
    st.rerun()


# ── Queue data builder ─────────────────────────────────────────────────────────

def _build_queue_rows(batch_results: pd.DataFrame, customers_df: Optional[pd.DataFrame], role: str) -> List[Dict[str, Any]]:
    if batch_results is None or batch_results.empty:
        return []
    id_verifications = st.session_state.get("id_verifications")
    rows: List[Dict[str, Any]] = []
    for _, row in batch_results.iterrows():
        result = row.to_dict()
        customer_id = _safe_str(result.get("customer_id"))
        customer = _get_customer_row(customers_df, customer_id)
        id_row = _get_related_row(id_verifications, customer_id)
        raw_name = _first_present(customer, "full_name", "customer_name", "name", "legal_name")
        if not raw_name:
            raw_name = _first_present(id_row, "name_on_document", "customer_name", "full_name")
        display_name = customer_id
        if raw_name:
            display_name = display_customer_name(raw_name, role)
        score = _confidence_score(result)
        rule_ids = _extract_rule_ids(result)
        flags = _build_flags(result, rule_ids)
        disposition = _safe_str(result.get("disposition")).upper() or "REVIEW"
        rows.append({
            "customer_id":          customer_id,
            "customer_name_raw":    raw_name or customer_id,
            "customer_name_display": display_name,
            "entity_type":          _entity_label(_first_present(customer, "entity_type")),
            "confidence_score":     score,
            "decision":             _decision_label(disposition),
            "disposition":          disposition,
            "flag_count":           len(flags),
            "flags":                ", ".join(flags) if flags else "-",
            "jurisdiction":         (_first_present(customer, "jurisdiction") or
                                     _safe_str(result.get("jurisdiction")) or "Unknown").upper(),
            "risk_rating":          (_first_present(customer, "risk_rating") or "Unknown").title(),
            "notes":                _safe_str(result.get("rationale", ""))[:120],
            "account_open_date":    _format_date(_first_present(customer, "account_open_date", "open_date")),
            "last_kyc_review_date": _format_date(_first_present(customer, "last_kyc_review_date", "kyc_date")),
            "date_of_birth":        _format_date(_first_present(customer, "date_of_birth", "dob")),
            "country_of_origin":    _first_present(customer, "country_of_origin", "nationality"),
            "incorporation_date":   _format_date(_first_present(customer, "incorporation_date", "registration_date")),
            "_id_row":              id_row,
        })
    return rows


# ── Ruleset editor (Admin only) ────────────────────────────────────────────────

def _reload_engine_from_session_data() -> None:
    from kyc_engine.engine import KYCComplianceEngine
    filename_map = {"customers": "customers_clean.csv", "screenings": "screenings_clean.csv",
                    "id_verifications": "id_verifications_clean.csv", "transactions": "transactions_clean.csv",
                    "documents": "documents_clean.csv", "beneficial_ownership": "beneficial_ownership_clean.csv"}
    temp_dir = Path(tempfile.mkdtemp(prefix="kyc_ruleset_reload_"))
    for df_key, filename in filename_map.items():
        df_value = (st.session_state.get("customers_df", st.session_state.get("customers"))
                    if df_key == "customers" else st.session_state.get(df_key))
        if isinstance(df_value, pd.DataFrame):
            df_value.copy().to_csv(temp_dir / filename, index=False)
    engine = KYCComplianceEngine(data_clean_dir=temp_dir)
    st.session_state.kyc_engine = engine
    st.session_state.customers_df = engine.customers.copy() if engine.customers is not None else pd.DataFrame()
    st.session_state.customers = st.session_state.customers_df.copy()
    st.session_state.screenings = engine.screenings.copy() if engine.screenings is not None else pd.DataFrame()
    st.session_state.id_verifications = engine.id_verifications.copy() if engine.id_verifications is not None else pd.DataFrame()
    st.session_state.transactions = engine.transactions.copy() if engine.transactions is not None else pd.DataFrame()
    st.session_state.documents = engine.documents.copy() if engine.documents is not None else pd.DataFrame()
    st.session_state.beneficial_ownership = (
        engine.beneficial_ownership.copy() if engine.beneficial_ownership is not None else pd.DataFrame()
    )
    st.session_state.engines_initialized = True
    st.session_state.data_dir = temp_dir


def _refresh_ruleset_globals(new_version: str) -> None:
    import kyc_audit.logger as am
    import kyc_dashboard.main as mm
    import kyc_dashboard.state as sm
    am.RULESET_VERSION = mm.RULESET_VERSION = sm.RULESET_VERSION = new_version


def _validate_ruleset_text(text: str) -> str:
    raw = json.loads(text)
    manifest = RulesetManifest.model_validate(raw)
    return json.dumps(manifest.model_dump(mode="json"), indent=2)


def _render_ruleset_editor(user: Dict[str, Any], logger: Any) -> None:
    st.markdown("### Ruleset Editor")
    st.caption("Validate and update the active ruleset used for new queue runs.")
    current_text = _RULESET_PATH.read_text(encoding="utf-8")
    if "dashboard_ruleset_editor_text" not in st.session_state:
        st.session_state.dashboard_ruleset_editor_text = current_text
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Reload Current File", key="dashboard_ruleset_reload"):
            st.session_state.dashboard_ruleset_editor_text = current_text
            st.rerun()
    with c2:
        st.caption("Active file: " + _RULESET_PATH.name)
    draft = st.text_area("Active ruleset JSON", key="dashboard_ruleset_editor_text", height=420)
    a1, a2 = st.columns(2)
    with a1:
        if st.button("Validate Draft", key="dashboard_ruleset_validate"):
            try:
                normalized = _validate_ruleset_text(draft)
                version = json.loads(normalized).get("version", "unknown")
                st.success("Ruleset is valid. Draft version: " + version)
            except Exception as exc:
                st.error("Validation failed: " + str(exc))
    with a2:
        if st.button("Save Ruleset", type="primary", key="dashboard_ruleset_save"):
            try:
                normalized = _validate_ruleset_text(draft)
                _RULESET_PATH.write_text(normalized + "\n", encoding="utf-8")
                st.session_state.dashboard_ruleset_editor_text = normalized
                reset_ruleset_cache()
                new_version = get_active_ruleset_version()
                _refresh_ruleset_globals(new_version)
                if st.session_state.get("engines_initialized"):
                    _reload_engine_from_session_data()
                for k in ["batch_results", "batch_id", "batch_run_at", "dashboard_last_viewed_customer"]:
                    st.session_state[k] = None
                if logger:
                    logger.log("RULESET_UPDATED", details={"updated_by": user["username"],
                               "ruleset_version": new_version, "ruleset_file": _RULESET_PATH.name})
                st.success("Ruleset updated to " + new_version + ". Run the queue again to refresh decisions.")
                st.rerun()
            except Exception as exc:
                st.error("Ruleset update failed: " + str(exc))


def _render_admin_tools(user: Dict[str, Any], role: str, logger: Any) -> None:
    if role != "Admin":
        return
    st.divider()
    st.markdown("### Admin Controls")
    audit_tab, ruleset_tab = st.tabs(["Audit Trail", "Ruleset Editor"])
    with audit_tab:
        audit_trail.render(user, role, logger)
    with ruleset_tab:
        _render_ruleset_editor(user, logger)


# ── Identity detail (in expander) ─────────────────────────────────────────────

def _render_identity_expander(queue_row: Dict[str, Any], role: str) -> None:
    customer_id = queue_row["customer_id"]
    id_row = queue_row.get("_id_row") or {}
    identity_rows = [
        {"Field": "Legal Name",       "Value": queue_row["customer_name_display"]},
        {"Field": "Customer ID",      "Value": customer_id},
        {"Field": "Entity Type",      "Value": queue_row["entity_type"]},
        {"Field": "Jurisdiction",     "Value": queue_row["jurisdiction"]},
        {"Field": "Country of Origin","Value": queue_row["country_of_origin"] or "-"},
        {"Field": "Risk Rating",      "Value": queue_row["risk_rating"]},
    ]
    if queue_row["entity_type"] == "Corporate":
        identity_rows.append({"Field": "Incorporation Date", "Value": queue_row["incorporation_date"]})
    else:
        dob = queue_row.get("date_of_birth", "-")
        identity_rows.append({"Field": "Date of Birth",
                               "Value": mask(dob, "dob") if dob != "-" else "-"})
    identity_rows.extend([
        {"Field": "Account Opened",   "Value": queue_row["account_open_date"]},
        {"Field": "Last KYC Review",  "Value": queue_row["last_kyc_review_date"]},
        {"Field": "ID Type",          "Value": _entity_label(_first_present(id_row, "document_type")) if id_row else "-"},
        {"Field": "Document Number",  "Value": mask(_first_present(id_row, "document_number", "document_id"), "account") if id_row else "-"},
        {"Field": "ID Expiry",        "Value": _format_date(_first_present(id_row, "expiry_date")) if id_row else "-"},
        {"Field": "ID Verification",  "Value": _first_present(id_row, "document_status", "verification_status").upper() or "-"},
    ])
    with st.expander("Profile · Identity", expanded=False):
        st_dataframe_safe(pd.DataFrame(identity_rows), use_container_width=True, hide_index=True)


# ── Remediation panel ──────────────────────────────────────────────────────────

_FALSE_POSITIVE_CODES = [
    "FP-001 Legitimate PEP / public figure",
    "FP-002 Name match — different individual",
    "FP-003 Stale adverse media — resolved",
    "FP-004 Domestic transaction flagged in error",
    "FP-005 Other — see note",
]


def _render_remediation(queue_row: Dict[str, Any], result: Dict[str, Any], user: Dict[str, Any], role: str, logger: Any) -> None:
    disposition = queue_row.get("disposition", "REVIEW")
    customer_id = queue_row["customer_id"]
    score = queue_row["confidence_score"]
    rule_ids = _extract_rule_ids(result)

    if disposition not in ("REJECT", "REVIEW"):
        return
    if role not in ("Analyst", "Manager", "Admin", "Banker"):
        return

    st.divider()
    st.markdown("**Remediation Actions**")
    rc1, rc2 = st.columns(2)
    with rc1:
        reason = st.selectbox("Reason Code", ["— Select —"] + _FALSE_POSITIVE_CODES, key=f"r_{customer_id}")
    with rc2:
        note_text = st.text_input("Note (required)", key=f"n_{customer_id}")
    ec1, ec2 = st.columns(2)
    with ec1:
        if st.button("Escalate", key=f"esc_{customer_id}"):
            if not note_text.strip():
                st.error("Note required to escalate.")
            else:
                if logger:
                    logger.log("CUSTOMER_ESCALATED", customer_id=customer_id,
                               details={"note": note_text, "score": score, "disposition": disposition})
                st.success(f"{customer_id} escalated. Logged.")
    with ec2:
        if st.button("Propose Clear", key=f"clr_{customer_id}"):
            if reason == "— Select —" or not note_text.strip():
                st.error("Reason code and note required.")
            else:
                if logger:
                    logger.log("CLEAR_PROPOSED", customer_id=customer_id,
                               details={"reason_code": reason, "note": note_text,
                                        "disposition": disposition, "requires_manager_approval": True})
                st.success("Clear proposed. Awaiting manager approval.")


# ── Main render ────────────────────────────────────────────────────────────────

def render(user: Dict[str, Any], role: str, logger: Any) -> None:
    # Inject design CSS
    st.markdown(_DASH_CSS, unsafe_allow_html=True)

    # Page header
    ph1, ph2 = st.columns([3, 1])
    with ph1:
        st.markdown(
            "<div style='font-size:11px;color:rgba(255,255,255,0.35);text-transform:uppercase;"
            "letter-spacing:0.1em;margin-bottom:2px'>KYC Operations</div>"
            "<div style='font-size:22px;font-weight:600;letter-spacing:-0.02em;color:#f3f4f7;"
            "margin-bottom:2px'>Customer queue</div>"
            "<div style='font-size:13px;color:rgba(255,255,255,0.40)'>"
            f"{datetime.now().strftime('%a, %d %b %Y')}</div>",
            unsafe_allow_html=True,
        )

    if not st.session_state.get("engines_initialized"):
        st.warning("No data loaded yet. Use Data & Documents to load customer files before running the queue.")
        _render_admin_tools(user, role, logger)
        return

    # Institution picker + run button
    institutions = _get_available_institutions()
    institution_labels = [label for _, label in institutions]
    configured = get_configured_institution()
    default_index = 0
    if configured and configured in [iid for iid, _ in institutions]:
        default_index = [iid for iid, _ in institutions].index(configured)

    with ph2:
        st.markdown("<div style='padding-top:12px'></div>", unsafe_allow_html=True)
        if st.button("Run queue", type="primary", use_container_width=True, key="dashboard_run_queue"):
            sel_label = st.session_state.get("dashboard_institution_label", institution_labels[default_index])
            sel_id = next((iid for iid, lbl in institutions if lbl == sel_label), "__none__")
            institution_id = None if sel_id == "__none__" else sel_id
            _run_dashboard_batch(user, logger, institution_id)

    sel_label = st.selectbox("Institution", institution_labels, index=default_index,
                             key="dashboard_institution_label", label_visibility="collapsed")

    if st.session_state.get("batch_results") is None:
        st.info("Run the queue to evaluate all customers and populate the dashboard.")
        _render_admin_tools(user, role, logger)
        return

    st.caption(
        "Last sync " + str(st.session_state.get("batch_run_at", "-"))
        + " · batch " + str(st.session_state.get("batch_id", "-"))
    )

    # Build queue rows
    batch_results = st.session_state.get("batch_results")
    customers_df  = st.session_state.get("customers_df")
    all_rows = _build_queue_rows(batch_results, customers_df, role)

    if not all_rows:
        st.info("No customers in the current queue run.")
        _render_admin_tools(user, role, logger)
        return

    # KPI strip
    queue_df_tmp = pd.DataFrame(all_rows)
    st.markdown(_kpi_strip_html(queue_df_tmp), unsafe_allow_html=True)

    # ── Filter row ─────────────────────────────────────────────────────────────
    if "dashboard_filter" not in st.session_state:
        st.session_state.dashboard_filter = "all"

    chip_labels = [
        ("all",    "All"),
        ("review", "Needs review"),
        ("high",   "High risk"),
        ("pass",   "Cleared"),
    ]
    filt_cols = st.columns(len(chip_labels) + 2)
    for i, (val, label) in enumerate(chip_labels):
        with filt_cols[i]:
            active = st.session_state.dashboard_filter == val
            btn_type = "primary" if active else "secondary"
            if st.button(label, key=f"chip_{val}", type=btn_type, use_container_width=True):
                st.session_state.dashboard_filter = val
                st.rerun()
    with filt_cols[-2]:
        search_term = st.text_input("Search", placeholder="ID / name / jurisdiction",
                                    key="dashboard_search", label_visibility="collapsed")
    with filt_cols[-1]:
        st.markdown("<div style='padding-top:4px'></div>", unsafe_allow_html=True)

    # Apply filters
    filtered_rows = all_rows[:]
    current_filter = st.session_state.dashboard_filter
    if current_filter == "review":
        filtered_rows = [r for r in filtered_rows if r["disposition"] in ("REJECT", "REVIEW")]
    elif current_filter == "high":
        filtered_rows = [r for r in filtered_rows if _risk_level(r["confidence_score"]) >= 4]
    elif current_filter == "pass":
        filtered_rows = [r for r in filtered_rows if r["disposition"] in ("PASS", "PASS_WITH_NOTES")]
    if search_term.strip():
        needle = search_term.strip().lower()
        filtered_rows = [
            r for r in filtered_rows
            if needle in r["customer_id"].lower()
            or needle in r["customer_name_raw"].lower()
            or needle in r["jurisdiction"].lower()
        ]

    if not filtered_rows:
        st.info("No customers match the current filters.")
        _render_admin_tools(user, role, logger)
        return

    st.caption(f"Showing {len(filtered_rows)} of {len(all_rows)} customers")

    # ── Main 3/2 split ─────────────────────────────────────────────────────────
    selected_id = st.session_state.get("dashboard_selected_customer_id")
    filtered_ids = [r["customer_id"] for r in filtered_rows]
    if selected_id not in filtered_ids:
        selected_id = filtered_ids[0]
        st.session_state.dashboard_selected_customer_id = selected_id

    left_col, right_col = st.columns([3, 2], gap="large")

    # LEFT — styled client list
    with left_col:
        st.markdown(_client_list_html(filtered_rows, selected_id), unsafe_allow_html=True)

        # Selectbox for actual navigation (label hidden, just functional)
        selected_id = st.selectbox(
            "Open customer record",
            filtered_ids,
            index=filtered_ids.index(selected_id),
            format_func=lambda cid: next(
                (r["customer_name_display"] + " · " + cid
                 for r in filtered_rows if r["customer_id"] == cid), cid
            ),
            key="dashboard_selected_customer_widget",
        )
        st.session_state.dashboard_selected_customer_id = selected_id

    # RIGHT — case detail
    selected_row = next((r for r in filtered_rows if r["customer_id"] == selected_id), filtered_rows[0])
    selected_result = _result_lookup(batch_results, selected_id)

    last_viewed = st.session_state.get("dashboard_last_viewed_customer")
    if last_viewed != selected_id and logger:
        logger.log("CUSTOMER_VIEW", customer_id=selected_id,
                   details={"tab": "dashboard", "ruleset_version": _safe_str(selected_result.get("ruleset_version")) or get_active_ruleset_version()},
                   snapshot={f: selected_result.get(f) for f in _SNAPSHOT_FIELDS if f in selected_result})
        st.session_state.dashboard_last_viewed_customer = selected_id

    with right_col:
        # Navigation bar
        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("← Prev", key="dashboard_prev_customer", use_container_width=True):
                idx = filtered_ids.index(selected_id)
                st.session_state.dashboard_selected_customer_id = filtered_ids[(idx - 1) % len(filtered_ids)]
                st.rerun()
        with nav2:
            st.caption(f"Record {filtered_ids.index(selected_id) + 1} of {len(filtered_ids)}")
        with nav3:
            if st.button("Next →", key="dashboard_next_customer", use_container_width=True):
                idx = filtered_ids.index(selected_id)
                st.session_state.dashboard_selected_customer_id = filtered_ids[(idx + 1) % len(filtered_ids)]
                st.rerun()

        # Detail header (name, KPIs, badge)
        st.markdown(_detail_header_html(selected_row), unsafe_allow_html=True)

        # Confidence gauge
        score = selected_row["confidence_score"]
        gauge_color = (
            "oklch(72% 0.14 155)" if score >= 70
            else "oklch(80% 0.14 80)" if score >= 50
            else "oklch(72% 0.16 27)"
        )
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100", "font": {"size": 22}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "rgba(255,255,255,0.2)"},
                "bar":  {"color": gauge_color, "thickness": 0.28},
                "bgcolor": "rgba(0,0,0,0)",
                "steps": [
                    {"range": [0, 50],   "color": "rgba(213,94,0,0.10)"},
                    {"range": [50, 70],  "color": "rgba(230,159,0,0.10)"},
                    {"range": [70, 100], "color": "rgba(0,158,115,0.10)"},
                ],
                "threshold": {"line": {"color": gauge_color, "width": 3}, "thickness": 0.75, "value": score},
            },
            title={"text": "Confidence score", "font": {"size": 12}},
        ))
        gauge_fig.update_layout(
            height=200, margin=dict(l=20, r=20, t=30, b=5),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(gauge_fig, use_container_width=True)

        # "What needs attention" — triggered rules as flag rows
        attn_html = _needs_attention_html(selected_result)
        if attn_html:
            st.markdown(attn_html, unsafe_allow_html=True)

        # KYC dimension flag rows
        dim_html = _dimension_flags_html(selected_result)
        if dim_html:
            st.markdown(dim_html, unsafe_allow_html=True)

        # Identity (in expander)
        _render_identity_expander(selected_row, role)

        # Remediation
        _render_remediation(selected_row, selected_result, user, role, logger)

    # Admin-only tools at the bottom
    _render_admin_tools(user, role, logger)
