"""
kyc_dashboard/tabs/dashboard.py
--------------------------------
KYC Operations dashboard — HNWI design system (faithful to design prototype).
Visual language: styles.css tokens · KPI strip · flag-row dimensions · risk bars.
Backend logic is unchanged — only CSS/HTML generation is replaced.
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

# ── Design-system CSS (faithful port of styles.css, hex colors for universal support) ─

_DASH_CSS = """
<style>
/* ── Design tokens ── */
:root {
  --bg: #ffffff;
  --bg-elev: #f8f9fb;
  --bg-sunken: #f3f4f7;
  --bg-hover: #eeeef4;
  --bg-active: #e5e6ed;
  --line: #e5e6ec;
  --line-strong: #d0d2dc;
  --ink: #0e1014;
  --ink-2: #23262f;
  --ink-3: #464b58;
  --ink-4: #666c7a;
  --ink-5: #8a8e9a;
  --accent:      #3b5bdb;
  --accent-soft: #eef1ff;
  --accent-ink:  #2f4abf;
  --ok:          #2b9a48;
  --ok-soft:     #eafbee;
  --warn:        #b87400;
  --warn-soft:   #fff8e0;
  --bad:         #c22828;
  --bad-soft:    #fff1f0;
  --info:        #1864ab;
  --info-soft:   #e7f5ff;
  --warn-text:   #8a5900;
  --risk-med:    #b07a00;
  --radius: 8px; --radius-sm: 6px; --radius-lg: 12px;
  --shadow-sm: 0 1px 2px rgba(15,17,22,.05), 0 0 0 1px rgba(15,17,22,.03);
  --shadow-md: 0 2px 8px rgba(15,17,22,.09), 0 0 0 1px rgba(15,17,22,.04);
  --d-row: 44px; --d-pad: 16px; --d-gap: 14px; --d-text: 13.5px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* ── Streamlit layout cleanup ── */
.main .block-container {
  padding-top: 0.75rem !important;
  padding-bottom: 2rem !important;
  max-width: 1440px !important;
}
div[data-testid="stAppViewContainer"] > section.main {
  background: var(--bg-sunken) !important;
}
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
  border: none !important;
  box-shadow: none !important;
}
/* Caption / small text */
div[data-testid="stCaptionContainer"] p {
  color: var(--ink-4) !important;
  font-size: 12px !important;
}

/* ── Filter chip buttons (override Streamlit secondary style) ── */
div[data-testid="stHorizontalBlock"] .stButton > button {
  border-radius: 999px !important;
  padding: 4px 14px !important;
  font-size: 12.5px !important;
  font-weight: 500 !important;
  height: auto !important;
  min-height: 30px !important;
  line-height: 1.4 !important;
  border: 1px solid var(--line-strong) !important;
  background: var(--bg) !important;
  color: var(--ink-3) !important;
  box-shadow: none !important;
  transition: background .12s, border-color .12s, color .12s !important;
}
div[data-testid="stHorizontalBlock"] .stButton > button:hover {
  background: var(--bg-hover) !important;
  border-color: var(--ink-5) !important;
  color: var(--ink-2) !important;
}
div[data-testid="stHorizontalBlock"] .stButton > button[kind="primary"] {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: #fff !important;
}
div[data-testid="stHorizontalBlock"] .stButton > button[kind="primary"]:hover {
  background: var(--accent-ink) !important;
}

/* ── Run queue + nav buttons ── */
.stButton > button[kind="primary"] {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: #fff !important;
  border-radius: var(--radius) !important;
  font-weight: 500 !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--accent-ink) !important;
  border-color: var(--accent-ink) !important;
}
.stButton > button[kind="secondary"] {
  border-radius: var(--radius) !important;
  border-color: var(--line-strong) !important;
  color: var(--ink-3) !important;
  background: var(--bg) !important;
  font-weight: 400 !important;
}

/* ── Search input ── */
div[data-testid="stTextInput"] input {
  border-radius: var(--radius) !important;
  border-color: var(--line-strong) !important;
  font-size: 13px !important;
  height: 36px !important;
  padding: 0 10px !important;
  background: var(--bg) !important;
  color: var(--ink) !important;
}
div[data-testid="stTextInput"] input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(59,91,219,.12) !important;
}

/* ── Selectbox ── */
div[data-testid="stSelectbox"] > div > div {
  border-radius: var(--radius) !important;
  border-color: var(--line-strong) !important;
  font-size: 13px !important;
  min-height: 36px !important;
  background: var(--bg) !important;
  color: var(--ink) !important;
}

/* ── Expander ── */
div[data-testid="stExpander"] {
  border: 1px solid var(--line) !important;
  border-radius: var(--radius-lg) !important;
  background: var(--bg) !important;
  box-shadow: var(--shadow-sm) !important;
  overflow: hidden !important;
}
div[data-testid="stExpander"] summary {
  font-size: 13px !important;
  font-weight: 500 !important;
  color: var(--ink) !important;
  padding: 10px 16px !important;
}

/* ── Plotly chart container ── */
div[data-testid="stPlotlyChart"] {
  border-radius: var(--radius-lg) !important;
  overflow: hidden !important;
}

/* ── Utilities ── */
.tnum  { font-variant-numeric: tabular-nums; }
.muted { color: var(--ink-3); }
.eyebrow {
  font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  color: var(--ink-4); font-weight: 500;
}
.row-flex     { display: flex; align-items: center; gap: 10px; }
.row-flex.gap-sm  { gap: 6px; }
.row-flex.between { justify-content: space-between; }
.divider { height: 1px; background: var(--line); margin: var(--d-gap) 0; }

/* ── Page header ── */
.page-h {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 24px; margin-bottom: 16px;
}
.page-title {
  font-size: 22px; font-weight: 600; letter-spacing: -.02em;
  margin: 4px 0; color: var(--ink);
}
.page-sub { color: var(--ink-3); font-size: 13px; }

/* ── Section header ── */
.section-h {
  display: flex; align-items: center; justify-content: space-between;
  margin: 6px 0 10px;
}
.section-h h3 { margin: 0; font-size: 14px; font-weight: 600; color: var(--ink); }
.section-h .meta { color: var(--ink-4); font-size: 12px; }

/* ── Cards ── */
.card {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  margin-bottom: 12px;
}
.card-h {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--line);
  background: var(--bg-elev);
}
.card-h h3 {
  margin: 0; font-size: 13px; font-weight: 600;
  letter-spacing: -.005em; color: var(--ink);
}
.card-h .meta { color: var(--ink-4); font-size: 12px; }

/* ── KPI strip ── */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--d-gap);
  margin-bottom: var(--d-gap);
}
.kpi {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 16px 18px 18px;
  position: relative;
  overflow: hidden;
}
.kpi-label { font-size: 11.5px; color: var(--ink-4); font-weight: 500; text-transform: uppercase; letter-spacing: .04em; }
.kpi-value {
  font-size: 28px; font-weight: 600; letter-spacing: -.03em;
  margin-top: 6px; font-variant-numeric: tabular-nums; color: var(--ink);
  line-height: 1.1;
}
.kpi-sub   { font-size: 12px; color: var(--ink-4); margin-top: 4px; }
.kpi-delta {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; padding: 2px 6px; border-radius: 4px;
  margin-left: 8px; vertical-align: 3px; font-variant-numeric: tabular-nums;
}
.kpi-delta.up      { color: var(--ok);    background: var(--ok-soft); }
.kpi-delta.down    { color: var(--bad);   background: var(--bad-soft); }
.kpi-delta.neutral { color: var(--ink-3); background: var(--bg-sunken); }

/* ── Badges ── */
.badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 9px; border-radius: 999px;
  font-size: 11.5px; font-weight: 500; line-height: 1.5; white-space: nowrap;
}
.badge .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex: 0 0 auto; }
.b-ok     { color: var(--ok);          background: var(--ok-soft); }
.b-warn   { color: var(--warn-text);   background: var(--warn-soft); }
.b-bad    { color: var(--bad);         background: var(--bad-soft); }
.b-info   { color: var(--info);        background: var(--info-soft); }
.b-mute   { color: var(--ink-4);       background: var(--bg-sunken); }
.b-accent { color: var(--accent-ink);  background: var(--accent-soft); }

/* ── Risk bars (5 segment) ── */
.risk-bar {
  display: inline-grid;
  grid-template-columns: repeat(5, 4px);
  gap: 2px; vertical-align: middle; margin-right: 4px;
}
.risk-bar i {
  height: 10px; border-radius: 1px;
  background: var(--bg-active); display: block;
}
.risk-bar.r-1 i:nth-child(-n+1),
.risk-bar.r-2 i:nth-child(-n+2),
.risk-bar.r-3 i:nth-child(-n+3),
.risk-bar.r-4 i:nth-child(-n+4),
.risk-bar.r-5 i:nth-child(-n+5) { background: currentColor; }
.risk-low    { color: var(--ok); }
.risk-medium { color: var(--risk-med); }
.risk-high   { color: var(--bad); }

/* ── Table (client worklist) ── */
.tbl-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; }
.tbl thead th {
  text-align: left; font-weight: 500; font-size: 11px;
  color: var(--ink-4); text-transform: uppercase; letter-spacing: .07em;
  padding: 10px 14px; border-bottom: 1px solid var(--line);
  background: var(--bg-elev); white-space: nowrap;
}
.tbl tbody td {
  padding: 0 14px; height: var(--d-row);
  border-bottom: 1px solid var(--line);
  font-size: var(--d-text); vertical-align: middle; color: var(--ink);
}
.tbl tbody tr:last-child td { border-bottom: 0; }
.tbl tbody tr { cursor: pointer; transition: background .1s; }
.tbl tbody tr:hover { background: var(--bg-hover); }
.tbl tbody tr[data-selected="true"] { background: var(--accent-soft); }
.cell-client { display: flex; align-items: center; gap: 10px; }
.cell-client .ini {
  width: 30px; height: 30px; border-radius: 50%;
  background: var(--bg-active); color: var(--ink-2);
  display: grid; place-items: center;
  font-size: 11px; font-weight: 600; flex: 0 0 auto;
  letter-spacing: .03em;
}
.cell-client b   { font-weight: 500; display: block; line-height: 1.3; font-size: 13.5px; }
.cell-client small { color: var(--ink-4); font-size: 11.5px; display: block; }

/* ── Flag rows ── */
.flag-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-top: 1px solid var(--line);
  transition: background .1s;
}
.flag-row:first-child { border-top: 0; }
.flag-row:hover { background: var(--bg-hover); }
.flag-row .left { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
.flag-row .ico {
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--bg-sunken); display: grid; place-items: center;
  flex: 0 0 auto; font-size: 13px; color: var(--ink-4);
}
.flag-row .ico.ok   { background: var(--ok-soft);   color: var(--ok); }
.flag-row .ico.warn { background: var(--warn-soft);  color: var(--warn-text); }
.flag-row .ico.bad  { background: var(--bad-soft);   color: var(--bad); }
.flag-row .t { font-size: 13px; font-weight: 500; color: var(--ink); }
.flag-row .s { font-size: 11.5px; color: var(--ink-4); margin-top: 1px; }
</style>
"""

# ── Hex gauge colors (Plotly does not support oklch) ──────────────────────────
_GAUGE_GREEN = "#00c285"
_GAUGE_AMBER = "#c9a600"
_GAUGE_RED   = "#e05c00"


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
    """Map 0-100 confidence score to 1-5 risk level (inverted — lower score = higher risk)."""
    if score >= 85:
        return 1
    if score >= 70:
        return 2
    if score >= 55:
        return 3
    if score >= 40:
        return 4
    return 5


def _disposition_tone(disposition: str) -> str:
    d = str(disposition).upper()
    if d == "PASS":
        return "ok"
    if d in ("PASS_WITH_NOTES", "REVIEW"):
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

def _ini_html(name: str) -> str:
    parts = name.upper().split()
    ini = (parts[0][0] + parts[-1][0]) if len(parts) >= 2 else name[:2].upper()
    return f"<div class='ini'>{ini}</div>"


def _badge_html(text: str, tone: str) -> str:
    cls = {"ok": "b-ok", "warn": "b-warn", "bad": "b-bad",
           "mute": "b-mute", "accent": "b-accent", "info": "b-info"}.get(tone, "b-mute")
    return f"<span class='badge {cls}'><span class='dot'></span>{text}</span>"


def _risk_bar_html(score: int) -> str:
    """5-segment risk bar using design CSS (.risk-bar .r-N .risk-level)."""
    level = _risk_level(score)
    cls = "risk-low" if level <= 2 else "risk-medium" if level == 3 else "risk-high"
    return f"<span class='risk-bar r-{level} {cls}'><i></i><i></i><i></i><i></i><i></i></span>"


def _kpi_strip_html(queue_df: pd.DataFrame) -> str:
    total        = len(queue_df)
    pass_count   = int((queue_df["decision"] == "PASS").sum()) if total else 0
    fail_count   = int((queue_df["decision"] == "FAIL").sum()) if total else 0
    review_count = int(queue_df["disposition"].isin(["REJECT", "REVIEW"]).sum()) if total else 0
    avg_score    = round(queue_df["confidence_score"].mean(), 1) if total else 0.0
    pass_rate    = int(round(pass_count / total * 100)) if total else 0

    cards = [
        {"label": "Open cases",          "value": str(total),       "sub": "in current queue run",            "delta": None},
        {"label": "Pass rate",           "value": f"{pass_rate}%",  "sub": f"{pass_count} customers cleared", "delta": None},
        {
            "label": "Require review",
            "value": str(review_count),
            "sub":   "REJECT or REVIEW disposition",
            "delta": ("down", f"{fail_count} hard fail") if fail_count > 0 else None,
        },
        {"label": "Avg. confidence",     "value": str(avg_score),   "sub": "out of 100",                      "delta": None},
    ]

    html = "<div class='kpi-strip'>"
    for c in cards:
        delta_html = ""
        if c["delta"]:
            delta_html = f"<span class='kpi-delta {c['delta'][0]}'>{c['delta'][1]}</span>"
        html += (
            f"<div class='kpi'>"
            f"<div class='kpi-label'>{c['label']}</div>"
            f"<div class='kpi-value'>{c['value']}{delta_html}</div>"
            f"<div class='kpi-sub'>{c['sub']}</div>"
            f"</div>"
        )
    html += "</div>"
    return html


def _client_list_html(rows: List[Dict[str, Any]], selected_id: str) -> str:
    html = (
        "<div class='section-h' style='margin-top:4px'>"
        "<h3>Active queue</h3>"
        f"<span class='meta'>{len(rows)} customers</span>"
        "</div>"
        "<div class='card'>"
        "<div class='tbl-wrap'><table class='tbl'>"
        "<thead><tr>"
        "<th>Client</th>"
        "<th style='width:100px'>Risk</th>"
        "<th style='width:120px;text-align:right'>Status</th>"
        "</tr></thead><tbody>"
    )
    for r in rows:
        sel = ' data-selected="true"' if r["customer_id"] == selected_id else ""
        ini  = _ini_html(r.get("customer_name_raw") or r["customer_id"])
        rbar = _risk_bar_html(r["confidence_score"])
        tone = _disposition_tone(r.get("disposition", "REVIEW"))
        lbl  = r.get("disposition", "REVIEW").replace("_", " ").title()
        bdg  = _badge_html(lbl, tone)
        meta = r.get("entity_type", "")
        if r.get("jurisdiction"):
            meta += f"&nbsp;·&nbsp;{r['jurisdiction']}"
        html += (
            f"<tr{sel}>"
            f"<td><div class='cell-client'>{ini}"
            f"<div><b>{r['customer_name_display']}</b>"
            f"<small>{meta}</small></div></div></td>"
            f"<td><span class='row-flex gap-sm'>{rbar}"
            f"<span class='tnum' style='font-size:12px;color:var(--ink-4)'>{r['confidence_score']}</span></span></td>"
            f"<td style='text-align:right'>{bdg}</td>"
            "</tr>"
        )
    html += "</tbody></table></div></div>"
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
            "<div class='flag-row'>"
            "<div class='left'>"
            "<div class='ico bad'>✕</div>"
            f"<div><div class='t'>{name}</div><div class='s'>{desc}</div></div>"
            "</div>"
            "<span class='badge b-bad'><span class='dot'></span>Hard Reject</span>"
            "</div>"
        )
    for r in review_rules:
        name = _safe_str(r.get("name") or r.get("rule_id", ""))
        desc = _safe_str(r.get("description", ""))[:90]
        rows_html += (
            "<div class='flag-row'>"
            "<div class='left'>"
            "<div class='ico warn'>⚑</div>"
            f"<div><div class='t'>{name}</div><div class='s'>{desc}</div></div>"
            "</div>"
            "<span class='badge b-warn'><span class='dot'></span>Review</span>"
            "</div>"
        )
    return (
        "<div class='section-h'>"
        "<h3>What needs attention</h3>"
        f"<span class='meta'>{len(reject_rules) + len(review_rules)} triggered</span>"
        "</div>"
        f"<div class='card'>{rows_html}</div>"
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
            (result.get(details_field) or {}).get("finding", "")
            if isinstance(result.get(details_field), dict) else ""
        )
        if not finding:
            finding = f"Score: {int(s)}/100"

        if s >= 70:
            ico_cls, ico_char, btone, blbl = "ok",   "✓", "ok",   "Pass"
        elif s >= 50:
            ico_cls, ico_char, btone, blbl = "warn", "⚑", "warn", "Attention"
        else:
            ico_cls, ico_char, btone, blbl = "bad",  "✕", "bad",  "Fail"

        rows_html += (
            "<div class='flag-row'>"
            "<div class='left'>"
            f"<div class='ico {ico_cls}'>{ico_char}</div>"
            f"<div><div class='t'>{label}</div><div class='s'>{finding[:100]}</div></div>"
            "</div>"
            f"<span class='badge b-{btone}'><span class='dot'></span>{blbl} · {int(s)}</span>"
            "</div>"
        )
    if not any_shown:
        return ""
    return (
        "<div class='section-h'><h3>KYC dimensions</h3>"
        "<span class='meta'>click a dimension to drill in</span></div>"
        f"<div class='card'>{rows_html}</div>"
    )


def _detail_header_html(queue_row: Dict[str, Any]) -> str:
    score       = queue_row["confidence_score"]
    disposition = queue_row.get("disposition", "REVIEW")
    tone        = _disposition_tone(disposition)
    disp_label  = disposition.replace("_", " ").title()
    risk_level  = _risk_level(score)
    risk_labels = {1: "Very Low", 2: "Low", 3: "Medium", 4: "High", 5: "Very High"}
    n_flags     = queue_row.get("flag_count", 0)
    flag_note   = (
        f"<span class='badge b-bad' style='font-size:11px'><span class='dot'></span>{n_flags} flag{'s' if n_flags != 1 else ''}</span>"
        if n_flags > 0
        else "<span style='color:var(--ink-4);font-size:12px'>No flags</span>"
    )
    entity_meta = " &nbsp;·&nbsp; ".join(
        x for x in [queue_row["customer_id"], queue_row.get("entity_type",""), queue_row.get("jurisdiction","")] if x
    )

    return (
        f"<div style='display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px'>"
        f"<div>"
        f"<div class='eyebrow'>Case detail</div>"
        f"<div style='font-size:17px;font-weight:600;letter-spacing:-.015em;color:var(--ink);margin:3px 0 3px'>"
        f"{queue_row['customer_name_display']}</div>"
        f"<div style='font-size:12px;color:var(--ink-4)'>{entity_meta}</div>"
        f"</div>"
        f"<div style='padding-top:4px'>{_badge_html(disp_label, tone)}</div>"
        f"</div>"
        f"<div class='kpi-strip' style='grid-template-columns:repeat(3,1fr);margin-bottom:10px'>"
        f"<div class='kpi'>"
        f"<div class='kpi-label'>Confidence</div>"
        f"<div class='kpi-value' style='font-size:24px'>{score}</div>"
        f"<div class='kpi-sub'>out of 100</div>"
        f"</div>"
        f"<div class='kpi'>"
        f"<div class='kpi-label'>Risk level</div>"
        f"<div class='kpi-value' style='font-size:14px;margin-top:10px'>"
        f"{_risk_bar_html(score)}{risk_labels[risk_level]}</div>"
        f"</div>"
        f"<div class='kpi'>"
        f"<div class='kpi-label'>Open flags</div>"
        f"<div class='kpi-value' style='font-size:24px'>{n_flags}</div>"
        f"<div class='kpi-sub'>{flag_note}</div>"
        f"</div>"
        f"</div>"
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
        score    = _confidence_score(result)
        rule_ids = _extract_rule_ids(result)
        flags    = _build_flags(result, rule_ids)
        disposition = _safe_str(result.get("disposition")).upper() or "REVIEW"
        rows.append({
            "customer_id":           customer_id,
            "customer_name_raw":     raw_name or customer_id,
            "customer_name_display": display_name,
            "entity_type":           _entity_label(_first_present(customer, "entity_type")),
            "confidence_score":      score,
            "decision":              _decision_label(disposition),
            "disposition":           disposition,
            "flag_count":            len(flags),
            "flags":                 ", ".join(flags) if flags else "-",
            "jurisdiction":          (_first_present(customer, "jurisdiction") or
                                      _safe_str(result.get("jurisdiction")) or "Unknown").upper(),
            "risk_rating":           (_first_present(customer, "risk_rating") or "Unknown").title(),
            "notes":                 _safe_str(result.get("rationale", ""))[:120],
            "account_open_date":     _format_date(_first_present(customer, "account_open_date", "open_date")),
            "last_kyc_review_date":  _format_date(_first_present(customer, "last_kyc_review_date", "kyc_date")),
            "date_of_birth":         _format_date(_first_present(customer, "date_of_birth", "dob")),
            "country_of_origin":     _first_present(customer, "country_of_origin", "nationality"),
            "incorporation_date":    _format_date(_first_present(customer, "incorporation_date", "registration_date")),
            "_id_row":               id_row,
        })
    return rows


# ── Ruleset editor (Admin only) ────────────────────────────────────────────────

def _reload_engine_from_session_data() -> None:
    from kyc_engine.engine import KYCComplianceEngine
    filename_map = {
        "customers": "customers_clean.csv", "screenings": "screenings_clean.csv",
        "id_verifications": "id_verifications_clean.csv", "transactions": "transactions_clean.csv",
        "documents": "documents_clean.csv", "beneficial_ownership": "beneficial_ownership_clean.csv",
    }
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
        {"Field": "Legal Name",        "Value": queue_row["customer_name_display"]},
        {"Field": "Customer ID",       "Value": customer_id},
        {"Field": "Entity Type",       "Value": queue_row["entity_type"]},
        {"Field": "Jurisdiction",      "Value": queue_row["jurisdiction"]},
        {"Field": "Country of Origin", "Value": queue_row["country_of_origin"] or "-"},
        {"Field": "Risk Rating",       "Value": queue_row["risk_rating"]},
    ]
    if queue_row["entity_type"] == "Corporate":
        identity_rows.append({"Field": "Incorporation Date", "Value": queue_row["incorporation_date"]})
    else:
        dob = queue_row.get("date_of_birth", "-")
        identity_rows.append({"Field": "Date of Birth",
                               "Value": mask(dob, "dob") if dob != "-" else "-"})
    identity_rows.extend([
        {"Field": "Account Opened",  "Value": queue_row["account_open_date"]},
        {"Field": "Last KYC Review", "Value": queue_row["last_kyc_review_date"]},
        {"Field": "ID Type",         "Value": _entity_label(_first_present(id_row, "document_type")) if id_row else "-"},
        {"Field": "Document Number", "Value": mask(_first_present(id_row, "document_number", "document_id"), "account") if id_row else "-"},
        {"Field": "ID Expiry",       "Value": _format_date(_first_present(id_row, "expiry_date")) if id_row else "-"},
        {"Field": "ID Verification", "Value": _first_present(id_row, "document_status", "verification_status").upper() or "-"},
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
    score       = queue_row["confidence_score"]

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
    st.markdown(_DASH_CSS, unsafe_allow_html=True)

    # Page header
    ph1, ph2 = st.columns([3, 1])
    with ph1:
        st.markdown(
            "<div class='eyebrow'>KYC Operations</div>"
            "<h1 class='page-title'>Customer queue</h1>"
            f"<div class='page-sub'>High Net Worth Individuals &nbsp;·&nbsp; {datetime.now().strftime('%a, %d %b %Y')}</div>"
            "<div style='margin-bottom:16px'></div>",
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
            if st.button(label, key=f"chip_{val}", type="primary" if active else "secondary",
                         use_container_width=True):
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

    # LEFT — styled client worklist
    with left_col:
        st.markdown(_client_list_html(filtered_rows, selected_id), unsafe_allow_html=True)
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
    selected_row    = next((r for r in filtered_rows if r["customer_id"] == selected_id), filtered_rows[0])
    selected_result = _result_lookup(batch_results, selected_id)

    last_viewed = st.session_state.get("dashboard_last_viewed_customer")
    if last_viewed != selected_id and logger:
        logger.log("CUSTOMER_VIEW", customer_id=selected_id,
                   details={"tab": "dashboard",
                            "ruleset_version": _safe_str(selected_result.get("ruleset_version")) or get_active_ruleset_version()},
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

        # Detail header — name, mini KPI strip, disposition badge
        st.markdown(_detail_header_html(selected_row), unsafe_allow_html=True)

        # Confidence gauge — hex colors only (Plotly does not support oklch)
        score = selected_row["confidence_score"]
        gauge_color = (
            _GAUGE_GREEN if score >= 70
            else _GAUGE_AMBER if score >= 50
            else _GAUGE_RED
        )
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={"suffix": "/100", "font": {"size": 22}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "rgba(128,128,128,0.25)"},
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

        # Triggered rules (needs attention)
        attn_html = _needs_attention_html(selected_result)
        if attn_html:
            st.markdown(attn_html, unsafe_allow_html=True)

        # KYC dimension flag rows
        dim_html = _dimension_flags_html(selected_result)
        if dim_html:
            st.markdown(dim_html, unsafe_allow_html=True)

        # Identity profile (expander)
        _render_identity_expander(selected_row, role)

        # Remediation actions
        _render_remediation(selected_row, selected_result, user, role, logger)

    # Admin-only tools at the bottom
    _render_admin_tools(user, role, logger)
