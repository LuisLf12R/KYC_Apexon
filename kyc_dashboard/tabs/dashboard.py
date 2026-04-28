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
import streamlit.components.v1 as st_components

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


# ── Component data serialisation ──────────────────────────────────────────────

def _map_to_case_json(row: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    disposition = row.get("disposition", "REVIEW")
    score = row["confidence_score"]

    status_map = {
        "REJECT":         ("Escalated",       "bad"),
        "REVIEW":         ("Pending review",  "warn"),
        "PASS_WITH_NOTES":("Dual-approval",   "accent"),
        "PASS":           ("Cleared",         "ok"),
    }
    status_label, _ = status_map.get(disposition, ("Pending review", "warn"))

    sla_map = {
        "REJECT":          {"tone": "bad",  "label": "Action needed"},
        "REVIEW":          {"tone": "warn", "label": "Under review"},
        "PASS_WITH_NOTES": {"tone": "warn", "label": "Pending sign-off"},
        "PASS":            {"tone": "ok",   "label": "On track"},
    }

    risk = "low" if score >= 70 else "medium" if score >= 50 else "high"

    dim_fields = [
        ("identity",     "Identity verification", "identity_verification_score"),
        ("aml",          "AML / PEP screening",   "aml_screening_score"),
        ("ubo",          "Beneficial ownership",  "beneficial_ownership_score"),
        ("sow",          "Source of Wealth",      "source_of_wealth_score"),
        ("crs",          "CRS / FATCA",           "crs_fatca_score"),
        ("activity",     "Account activity",      "account_activity_score"),
        ("data_quality", "Data quality",          "data_quality_score"),
    ]
    dimensions = []
    for key, title, sf in dim_fields:
        s = int(round(_as_float(result.get(sf, 0))))
        if s > 0:
            tone = "ok" if s >= 70 else "warn" if s >= 50 else "bad"
            dimensions.append({"key": key, "title": title, "score": s,
                                "tone": tone, "sub": f"Score: {s} / 100"})

    reject_rules, review_rules = [], []
    for r in result.get("triggered_reject_rules", []) or []:
        reject_rules.append({
            "name": _safe_str(r.get("name") or r.get("rule_id", ""))[:60],
            "desc": _safe_str(r.get("description", ""))[:90],
        })
    for r in result.get("triggered_review_rules", []) or []:
        review_rules.append({
            "name": _safe_str(r.get("name") or r.get("rule_id", ""))[:60],
            "desc": _safe_str(r.get("description", ""))[:90],
        })

    name = row["customer_name_raw"] or row["customer_id"]
    parts = name.upper().split()
    ini = (parts[0][0] + parts[-1][0]) if len(parts) >= 2 else name[:2].upper()

    return {
        "id":           row["customer_id"],
        "client":       row["customer_name_display"],
        "ini":          ini,
        "tier":         row.get("risk_rating", "Standard"),
        "type":         row.get("entity_type", "Individual"),
        "jurisdiction": row.get("jurisdiction", "—"),
        "rm":           "Officer — J. Marlow",
        "status":       status_label,
        "risk":         risk,
        "riskScore":    score,
        "aum":          "—",
        "sla":          sla_map.get(disposition, {"tone": "warn", "label": "Under review"}),
        "flags":        [r["name"] for r in (reject_rules + review_rules)[:3]] or ["No flags"],
        "dimensions":   dimensions,
        "rejectRules":  reject_rules,
        "reviewRules":  review_rules,
        "rationale":    _safe_str(result.get("rationale", ""))[:200],
        "notes":        row.get("notes", "")[:120],
    }


def _build_component_data(queue_rows: List[Dict[str, Any]],
                          batch_results: pd.DataFrame,
                          batch_id: str,
                          run_at: str) -> Dict[str, Any]:
    cases = []
    for row in queue_rows:
        result = _result_lookup(batch_results, row["customer_id"])
        cases.append(_map_to_case_json(row, result))

    total = len(cases)
    pass_count   = sum(1 for r in queue_rows if r.get("decision") == "PASS")
    fail_count   = sum(1 for r in queue_rows if r.get("disposition") == "REJECT")
    review_count = sum(1 for r in queue_rows if r.get("disposition") in ("REJECT", "REVIEW"))
    avg_score    = round(sum(r["confidence_score"] for r in queue_rows) / max(total, 1), 1)
    pass_rate    = int(round(pass_count / max(total, 1) * 100))

    return {
        "cases": cases,
        "kpis": {
            "total": total,
            "passRate": pass_rate,
            "passCount": pass_count,
            "failCount": fail_count,
            "reviewCount": review_count,
            "avgScore": avg_score,
        },
        "batchId": batch_id,
        "runAt": run_at,
    }


# ── Full HTML component (React + design CSS, runs in iframe) ──────────────────

def _build_dashboard_html(component_data: Dict[str, Any]) -> str:
    data_json = json.dumps(component_data, default=str, ensure_ascii=False)

    css = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; font-family: "Helvetica Neue", Helvetica, Arial, ui-sans-serif, system-ui, sans-serif; background: #f6f6f8; -webkit-font-smoothing: antialiased; }
:root {
  --bg:#ffffff; --bg-elev:#fbfbfc; --bg-sunken:#f6f6f8; --bg-hover:#f3f3f6; --bg-active:#eeeef3;
  --line:#ececf0; --line-strong:#d8d8e0;
  --ink:#0e1014; --ink-2:#2a2d35; --ink-3:#4a4e59; --ink-4:#6a6e79; --ink-5:#8a8e98;
  --accent:#3b5bdb; --accent-soft:#eef1ff; --accent-ink:#2f4abf;
  --ok:#2b9a48; --ok-soft:#eafbee;
  --warn:#c07700; --warn-soft:#fff9e1; --warn-text:#8a5900;
  --bad:#c22828; --bad-soft:#fff1f0;
  --info:#1864ab; --info-soft:#e7f5ff;
  --risk-med:#b07a00;
  --radius:8px; --radius-sm:6px; --radius-lg:12px;
  --shadow-sm:0 1px 2px rgba(15,17,22,.05),0 0 0 1px rgba(15,17,22,.03);
  --shadow-md:0 2px 8px rgba(15,17,22,.09),0 0 0 1px rgba(15,17,22,.04);
  --d-row:44px; --d-pad:16px; --d-gap:16px; --d-text:14px;
  --font-mono:"SF Mono",Menlo,Consolas,monospace;
}
button { font:inherit; color:inherit; cursor:pointer; border:0; background:none; padding:0; }
input, textarea, select { font:inherit; color:inherit; }
.tnum  { font-variant-numeric:tabular-nums; }
.mono  { font-family:var(--font-mono); font-variant-numeric:tabular-nums; }
.muted { color:var(--ink-3); }
.eyebrow { font-size:11px; letter-spacing:.08em; text-transform:uppercase; color:var(--ink-4); font-weight:500; }
.row-flex { display:flex; align-items:center; gap:10px; }
.row-flex.gap-sm { gap:6px; }
.row-flex.between { justify-content:space-between; }
.col-flex { display:flex; flex-direction:column; gap:var(--d-gap); }
.divider  { height:1px; background:var(--line); margin:var(--d-gap) 0; }
.page-h   { display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-bottom:20px; }
.page-title { font-size:22px; font-weight:600; letter-spacing:-.02em; margin:4px 0; color:var(--ink); }
.page-sub   { color:var(--ink-3); font-size:13.5px; }
.section-h  { display:flex; align-items:center; justify-content:space-between; margin:6px 0 12px; }
.section-h h3 { margin:0; font-size:14px; font-weight:600; color:var(--ink); }
.section-h .meta { color:var(--ink-4); font-size:12px; }
.card { background:var(--bg); border:1px solid var(--line); border-radius:var(--radius-lg); box-shadow:var(--shadow-sm); overflow:hidden; margin-bottom:14px; }
.card-pad { padding:var(--d-pad) calc(var(--d-pad) + 4px); }
.card-h { display:flex; align-items:center; justify-content:space-between; padding:14px 18px; border-bottom:1px solid var(--line); }
.card-h h3 { margin:0; font-size:13.5px; font-weight:600; letter-spacing:-.005em; color:var(--ink); }
.card-h .meta { color:var(--ink-4); font-size:12px; }
.kpi-strip { display:grid; grid-template-columns:repeat(4,1fr); gap:var(--d-gap); margin-bottom:var(--d-gap); }
.kpi { background:var(--bg); border:1px solid var(--line); border-radius:var(--radius-lg); padding:16px 18px 18px; position:relative; overflow:hidden; }
.kpi-label { font-size:12px; color:var(--ink-3); display:flex; align-items:center; gap:6px; }
.kpi-value { font-size:28px; font-weight:600; letter-spacing:-.025em; margin-top:6px; font-variant-numeric:tabular-nums; color:var(--ink); }
.kpi-sub   { font-size:12px; color:var(--ink-4); margin-top:2px; }
.kpi-delta { display:inline-flex; align-items:center; gap:3px; font-size:11.5px; padding:2px 6px; border-radius:4px; margin-left:8px; vertical-align:3px; font-variant-numeric:tabular-nums; }
.kpi-delta.up   { color:var(--ok);   background:var(--ok-soft); }
.kpi-delta.down { color:var(--bad);  background:var(--bad-soft); }
.badge { display:inline-flex; align-items:center; gap:5px; padding:2px 8px; border-radius:999px; font-size:11.5px; font-weight:500; line-height:1.5; white-space:nowrap; }
.badge .dot { width:6px; height:6px; border-radius:50%; background:currentColor; flex:0 0 auto; }
.b-ok     { color:var(--ok);         background:var(--ok-soft); }
.b-warn   { color:var(--warn-text);  background:var(--warn-soft); }
.b-bad    { color:var(--bad);        background:var(--bad-soft); }
.b-info   { color:var(--info);       background:var(--info-soft); }
.b-mute   { color:var(--ink-3);      background:var(--bg-sunken); }
.b-accent { color:var(--accent-ink); background:var(--accent-soft); }
.risk-bar { display:inline-grid; grid-template-columns:repeat(5,4px); gap:2px; vertical-align:middle; margin-right:6px; }
.risk-bar i { height:10px; border-radius:1px; background:var(--bg-active); display:block; }
.risk-bar.r-1 i:nth-child(-n+1),.risk-bar.r-2 i:nth-child(-n+2),.risk-bar.r-3 i:nth-child(-n+3),.risk-bar.r-4 i:nth-child(-n+4),.risk-bar.r-5 i:nth-child(-n+5) { background:currentColor; }
.risk-low    { color:var(--ok); }
.risk-medium { color:var(--risk-med); }
.risk-high   { color:var(--bad); }
.tbl { width:100%; border-collapse:collapse; }
.tbl thead th { text-align:left; font-weight:500; font-size:11.5px; color:var(--ink-4); text-transform:uppercase; letter-spacing:.06em; padding:10px 14px; border-bottom:1px solid var(--line); background:var(--bg-elev); position:sticky; top:0; z-index:1; }
.tbl tbody td { padding:0 14px; height:var(--d-row); border-bottom:1px solid var(--line); font-size:var(--d-text); vertical-align:middle; color:var(--ink); }
.tbl tbody tr:last-child td { border-bottom:0; }
.tbl tbody tr { cursor:pointer; transition:background .12s; }
.tbl tbody tr:hover { background:var(--bg-hover); }
.tbl tbody tr[data-selected="true"] { background:var(--accent-soft); }
.cell-id { font-family:var(--font-mono); color:var(--ink-3); font-size:12px; }
.cell-client { display:flex; align-items:center; gap:10px; }
.cell-client .ini { width:28px; height:28px; border-radius:50%; background:var(--bg-active); color:var(--ink-2); display:grid; place-items:center; font-size:11px; font-weight:600; letter-spacing:0; flex:0 0 auto; }
.cell-client b { font-weight:500; display:block; line-height:1.2; }
.cell-client small { color:var(--ink-4); font-size:11.5px; }
.cell-num { font-variant-numeric:tabular-nums; font-family:var(--font-mono); }
.sla { display:inline-flex; align-items:center; gap:6px; font-variant-numeric:tabular-nums; font-size:12.5px; }
.sla.ok   { color:var(--ok); }
.sla.warn { color:var(--risk-med); }
.sla.bad  { color:var(--bad); }
.chips { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.chip { display:inline-flex; align-items:center; gap:6px; height:28px; padding:0 10px; border:1px solid var(--line); border-radius:999px; background:var(--bg); color:var(--ink-2); font-size:12.5px; transition:background .1s,border-color .1s,color .1s; }
.chip:hover { background:var(--bg-hover); }
.chip[data-active="true"] { border-color:var(--ink); background:var(--ink); color:var(--bg); }
.search { display:flex; align-items:center; gap:8px; background:var(--bg-sunken); border:1px solid var(--line); border-radius:8px; padding:0 12px; height:34px; color:var(--ink-3); transition:border-color .15s,box-shadow .15s; }
.search:focus-within { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); color:var(--ink); }
.search input { background:none; border:0; outline:0; flex:1; font-size:13.5px; min-width:0; }
.flag-row { display:flex; align-items:center; justify-content:space-between; padding:10px 14px; border-top:1px solid var(--line); transition:background .12s; }
.flag-row:first-child { border-top:0; }
.flag-row:hover { background:var(--bg-hover); }
.flag-row .left { display:flex; align-items:center; gap:12px; min-width:0; flex:1; }
.flag-row .ico { width:28px; height:28px; border-radius:7px; background:var(--bg-sunken); display:grid; place-items:center; flex:0 0 auto; font-size:13px; color:var(--ink-4); }
.flag-row .ico.bad  { background:var(--bad-soft);  color:var(--bad); }
.flag-row .ico.warn { background:var(--warn-soft); color:var(--warn-text); }
.flag-row .ico.info { background:var(--info-soft); color:var(--info); }
.flag-row .ico.ok   { background:var(--ok-soft);   color:var(--ok); }
.flag-row .t { font-size:13px; font-weight:500; color:var(--ink); }
.flag-row .s { font-size:12px; color:var(--ink-3); }
.tabs-priority { display:flex; align-items:stretch; gap:8px; padding-bottom:0; border-bottom:1px solid var(--line); margin-bottom:var(--d-gap); }
.tabs-priority .tab-primary { display:inline-flex; align-items:center; gap:8px; padding:10px 14px 10px 12px; background:var(--ink); color:var(--bg); border:1px solid var(--ink); border-radius:var(--radius) var(--radius) 0 0; font-size:13.5px; font-weight:600; cursor:pointer; margin-bottom:-1px; box-shadow:var(--shadow-sm); }
.tabs-priority .tab-primary:hover { opacity:.9; }
.tabs-priority .tab-pill { margin-left:4px; background:rgba(255,255,255,.18); color:var(--bg); font-size:11px; font-weight:500; padding:2px 8px; border-radius:999px; }
.tabs-priority .tabs-divider { width:1px; background:var(--line); margin:6px 6px 0; }
.tabs-priority .tab-secondary { padding:10px; background:transparent; border:0; border-bottom:2px solid transparent; color:var(--ink-4); font-size:12.5px; font-weight:500; cursor:pointer; margin-bottom:-1px; }
.tabs-priority .tab-secondary:hover { color:var(--ink-2); }
.tabs-priority .tab-secondary[aria-current="true"] { color:var(--ink); border-color:var(--ink); }
.approval { border:1px solid var(--line); border-radius:var(--radius-lg); background:var(--bg); padding:16px; display:flex; flex-direction:column; gap:12px; box-shadow:var(--shadow-sm); }
.approval h4 { margin:0; font-size:13px; font-weight:600; }
.approval .grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.approval textarea { width:100%; border:1px solid var(--line); background:var(--bg-sunken); border-radius:8px; padding:10px 12px; resize:vertical; font-size:13px; min-height:70px; outline:0; transition:border-color .15s,box-shadow .15s; color:var(--ink); }
.approval textarea:focus { border-color:var(--accent); background:var(--bg); box-shadow:0 0 0 3px var(--accent-soft); }
.btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; height:36px; padding:0 14px; border-radius:8px; font-size:13.5px; font-weight:500; border:1px solid var(--line); background:var(--bg); color:var(--ink); transition:background .12s,border-color .12s; cursor:pointer; }
.btn:hover { background:var(--bg-hover); }
.btn:disabled { opacity:.4; cursor:not-allowed; }
.btn.primary { background:var(--ink); color:var(--bg); border-color:var(--ink); }
.btn.primary:hover { background:var(--ink-2); }
.btn.danger  { color:var(--bad); border-color:var(--bad-soft); background:var(--bad-soft); }
.btn.danger:hover { background:#fce4e4; }
.btn.success { color:var(--ok); border-color:var(--ok-soft); background:var(--ok-soft); }
.btn.success:hover { background:#d8f5e1; }
.btn.ghost { background:transparent; border-color:transparent; }
.btn.ghost:hover { background:var(--bg-hover); }
.btn.full  { width:100%; }
.approver { display:flex; align-items:center; gap:10px; padding:10px; border:1px dashed var(--line); border-radius:8px; font-size:12.5px; }
.approver.signed { border-style:solid; background:var(--ok-soft); border-color:transparent; }
.avatar { width:30px; height:30px; border-radius:50%; background:linear-gradient(135deg,#7b8fff,#5a6fee); display:grid; place-items:center; color:white; font-size:11px; font-weight:600; flex:0 0 auto; }
.detail-grid { display:grid; grid-template-columns:minmax(0,1fr) 320px; gap:var(--d-gap); }
::-webkit-scrollbar { width:8px; height:8px; }
::-webkit-scrollbar-thumb { background:var(--line-strong); border-radius:999px; border:2px solid var(--bg-sunken); }
::-webkit-scrollbar-track { background:transparent; }
"""

    react_code = r"""
const { useState, useMemo } = React;
const DATA = window.__QUEUE_DATA__;

function Icon({ name, size = 14, color = "currentColor" }) {
  const s = { width: size, height: size };
  const p = { fill: "none", stroke: color, strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round", ...s };
  if (name === "check")    return <svg {...p} viewBox="0 0 16 16"><polyline points="2,8 6,12 14,4"/></svg>;
  if (name === "flag")     return <svg {...p} viewBox="0 0 16 16"><path d="M3 2v12M3 2h8l-2 4 2 4H3"/></svg>;
  if (name === "x")        return <svg {...p} viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>;
  if (name === "file")     return <svg {...p} viewBox="0 0 16 16"><path d="M4 2h5l3 3v9H4z"/><path d="M9 2v3h3"/><line x1="6" y1="8" x2="10" y2="8"/><line x1="6" y1="11" x2="10" y2="11"/></svg>;
  if (name === "chevronL") return <svg {...p} viewBox="0 0 16 16"><polyline points="10,3 5,8 10,13"/></svg>;
  if (name === "escalate") return <svg {...p} viewBox="0 0 16 16"><polyline points="8,12 8,4"/><polyline points="4,8 8,4 12,8"/></svg>;
  if (name === "search")   return <svg {...p} viewBox="0 0 16 16"><circle cx="7" cy="7" r="4"/><line x1="10.5" y1="10.5" x2="14" y2="14"/></svg>;
  return <span style={{fontSize:size}}>{name}</span>;
}

function RiskBar({ risk, score }) {
  const n = { low: 1, medium: 3, high: 5 }[risk] || 1;
  const cls = risk === "low" ? "risk-low" : risk === "medium" ? "risk-medium" : "risk-high";
  return (
    <span className="row-flex gap-sm">
      <span className={`risk-bar r-${n} ${cls}`}><i/><i/><i/><i/><i/></span>
      <span className="tnum" style={{fontSize:12.5,color:"var(--ink-4)"}}>{score}</span>
    </span>
  );
}

function KpiStrip({ kpis }) {
  const cards = [
    { label:"Open cases",      value: kpis.total,          sub:"in current queue run" },
    { label:"Pass rate",       value: kpis.passRate + "%", sub:`${kpis.passCount} customers cleared` },
    { label:"Require review",  value: kpis.reviewCount,    sub:"REJECT or REVIEW disposition",
      delta: kpis.failCount > 0 ? { cls:"down", text:`${kpis.failCount} hard fail` } : null },
    { label:"Avg. confidence", value: kpis.avgScore,       sub:"out of 100" },
  ];
  return (
    <div className="kpi-strip">
      {cards.map((c, i) => (
        <div className="kpi" key={i}>
          <div className="kpi-label">{c.label}</div>
          <div className="kpi-value">
            {c.value}
            {c.delta && <span className={`kpi-delta ${c.delta.cls}`}>{c.delta.text}</span>}
          </div>
          <div className="kpi-sub">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}

function CasePanel({ c, onBack }) {
  const [tab, setTab]         = useState("reconcile");
  const [signoffA, setSignoffA] = useState(false);
  const [signoffB, setSignoffB] = useState(false);
  const [note, setNote]       = useState("");
  const [decision, setDecision] = useState(null);

  if (!c) return (
    <div style={{padding:"60px 20px",textAlign:"center",color:"var(--ink-4)"}}>
      <div style={{fontSize:32,marginBottom:12}}>←</div>
      <div style={{fontSize:14,fontWeight:500,color:"var(--ink)"}}>Select a case</div>
      <div style={{fontSize:13,marginTop:4}}>Click a row in the queue to view details</div>
    </div>
  );

  const badgeCls = c.status==="Escalated" ? "b-bad" : c.status==="Dual-approval" ? "b-accent" : c.status==="Cleared" ? "b-ok" : c.status==="Awaiting docs" ? "b-warn" : "b-mute";
  const totalFlags = c.rejectRules.length + c.reviewRules.length;

  return (
    <div>
      <div className="page-h" style={{marginBottom:12}}>
        <div>
          <div className="row-flex" style={{marginBottom:6}}>
            <button className="btn ghost" onClick={onBack} style={{height:28,padding:"0 8px",gap:4}}>
              <Icon name="chevronL" size={12}/> Back
            </button>
            <span className="cell-id mono">{c.id}</span>
          </div>
          <h1 className="page-title" style={{fontSize:18,marginBottom:2}}>{c.client}</h1>
          <div className="page-sub">{c.tier} · {c.type} · {c.jurisdiction} · RM {c.rm.split(" — ")[1]||c.rm}</div>
        </div>
        <div><span className={`badge ${badgeCls}`}><span className="dot"/>{c.status}</span></div>
      </div>

      <div className="kpi-strip" style={{gridTemplateColumns:"repeat(3,1fr)",marginBottom:12}}>
        <div className="kpi">
          <div className="kpi-label">Risk score</div>
          <div className="kpi-value">{c.riskScore}<span className="muted" style={{fontSize:14,marginLeft:4}}>/100</span></div>
          <div className="kpi-sub" style={{marginTop:6}}><RiskBar risk={c.risk} score={c.risk.toUpperCase()}/></div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Entity type</div>
          <div className="kpi-value" style={{fontSize:16,paddingTop:6}}>{c.type}</div>
          <div className="kpi-sub">{c.jurisdiction}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Open flags</div>
          <div className="kpi-value">{totalFlags}</div>
          <div className="kpi-sub" style={{whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>
            {totalFlags > 0 ? (c.rejectRules[0]||c.reviewRules[0]).name : "No flags"}
          </div>
        </div>
      </div>

      <div className="tabs-priority">
        <button className="tab-primary" aria-current={tab==="reconcile"} onClick={()=>setTab("reconcile")}>
          <Icon name="check" size={13}/> Reconcile &amp; status
          {totalFlags > 0 && <span className="tab-pill">{totalFlags} to review</span>}
        </button>
        <span className="tabs-divider"/>
        <button className="tab-secondary" aria-current={tab==="overview"} onClick={()=>setTab("overview")}>Overview</button>
        <button className="tab-secondary" aria-current={tab==="documents"} onClick={()=>setTab("documents")}>Documents</button>
      </div>

      <div className="detail-grid">
        <div>
          {tab==="overview" && (
            <div className="card">
              <div className="card-h"><h3>KYC dimensions</h3><span className="meta">click to drill in</span></div>
              {c.dimensions.map((d,i)=>(
                <div className="flag-row" key={d.key} style={{borderTop:i?"1px solid var(--line)":"0"}}>
                  <div className="left">
                    <div className={`ico ${d.tone==="ok"?"ok":d.tone==="bad"?"bad":"warn"}`}>
                      <Icon name={d.tone==="ok"?"check":"flag"}/>
                    </div>
                    <div><div className="t">{d.title}</div><div className="s">{d.sub}</div></div>
                  </div>
                  <span className={`badge ${d.tone==="ok"?"b-ok":d.tone==="bad"?"b-bad":"b-warn"}`}>
                    <span className="dot"/>{d.tone==="ok"?"Pass":d.tone==="bad"?"Fail":"Attention"} · {d.score}
                  </span>
                </div>
              ))}
              {c.dimensions.length===0 && <div style={{padding:"24px 16px",color:"var(--ink-4)",fontSize:13}}>No dimension scores available</div>}
            </div>
          )}

          {tab==="documents" && (
            <div className="card">
              <div className="card-h"><h3>Documents</h3><span className="meta">on file</span></div>
              {[
                {n:"Identity document",s:"On file",tone:"ok"},
                {n:"Proof of address",s:"On file",tone:"ok"},
                {n:"Source of wealth documentation",s:"On file",tone:"ok"},
              ].map((d,i)=>(
                <div className="flag-row" key={i} style={{borderTop:i?"1px solid var(--line)":"0"}}>
                  <div className="left">
                    <div className="ico"><Icon name="file"/></div>
                    <div><div className="t">{d.n}</div></div>
                  </div>
                  <span className="badge b-ok"><span className="dot"/>{d.s}</span>
                </div>
              ))}
            </div>
          )}

          {tab==="reconcile" && (
            <>
              {totalFlags > 0 && (
                <div className="card">
                  <div className="card-h">
                    <h3>What needs attention</h3>
                    <span className="meta">{totalFlags} triggered</span>
                  </div>
                  {c.rejectRules.map((r,i)=>(
                    <div className="flag-row" key={"rej"+i}>
                      <div className="left">
                        <div className="ico bad"><Icon name="x"/></div>
                        <div><div className="t">{r.name}</div><div className="s">{r.desc}</div></div>
                      </div>
                      <span className="badge b-bad"><span className="dot"/>Hard Reject</span>
                    </div>
                  ))}
                  {c.reviewRules.map((r,i)=>(
                    <div className="flag-row" key={"rev"+i}>
                      <div className="left">
                        <div className="ico warn"><Icon name="flag"/></div>
                        <div><div className="t">{r.name}</div><div className="s">{r.desc}</div></div>
                      </div>
                      <span className="badge b-warn"><span className="dot"/>Review</span>
                    </div>
                  ))}
                </div>
              )}
              {c.rationale && (
                <div className="card">
                  <div className="card-h"><h3>Decision rationale</h3></div>
                  <div style={{padding:"12px 16px",fontSize:13,color:"var(--ink-3)",lineHeight:1.6}}>{c.rationale}</div>
                </div>
              )}
              {totalFlags===0 && !c.rationale && (
                <div className="card">
                  <div style={{padding:"40px 16px",textAlign:"center"}}>
                    <div style={{fontSize:28,color:"var(--ok)",marginBottom:8}}>✓</div>
                    <div style={{fontSize:14,fontWeight:500,color:"var(--ink)"}}>No issues found</div>
                    <div style={{fontSize:13,color:"var(--ink-4)",marginTop:4}}>All checks passed for this customer</div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="col-flex">
          <div className="approval">
            <div className="row-flex between">
              <h4>Decision</h4>
              <span className={`badge ${badgeCls}`}><span className="dot"/>{c.status}</span>
            </div>
            <div className="muted" style={{fontSize:13}}>
              {c.status==="Escalated" ? "Case escalated — requires senior review." :
               c.status==="Dual-approval" ? "UHNW threshold requires sign-off from two officers." :
               c.status==="Cleared" ? "Customer has cleared KYC review." :
               "Case is pending review by compliance officer."}
            </div>
            <div className={`approver${signoffA?" signed":""}`}>
              <div className="avatar" style={{width:26,height:26,fontSize:10}}>JM</div>
              <div style={{flex:1}}>
                <b>J. Marlow</b>
                <div className="muted" style={{fontSize:11.5}}>{signoffA?"Signed · 14:22":"Awaiting signature"}</div>
              </div>
              {!signoffA && <button className="btn" style={{height:28}} onClick={()=>setSignoffA(true)}>Sign</button>}
              {signoffA && <Icon name="check" color="var(--ok)"/>}
            </div>
            <div className={`approver${signoffB?" signed":""}`}>
              <div className="avatar" style={{width:26,height:26,fontSize:10,background:"linear-gradient(135deg,#c07040,#e08040)"}}>KT</div>
              <div style={{flex:1}}>
                <b>K. Tran</b>
                <div className="muted" style={{fontSize:11.5}}>{signoffB?"Signed · 14:31":"Pending"}</div>
              </div>
              {!signoffB && <button className="btn" style={{height:28}} onClick={()=>setSignoffB(true)} disabled={!signoffA}>Sign</button>}
              {signoffB && <Icon name="check" color="var(--ok)"/>}
            </div>
            <textarea placeholder="Decision rationale…" value={note} onChange={e=>setNote(e.target.value)}/>
            <div className="grid">
              <button className="btn success" onClick={()=>setDecision("approve")} disabled={!signoffA||!signoffB}>
                <Icon name="check"/> Approve
              </button>
              <button className="btn danger" onClick={()=>setDecision("reject")}>
                <Icon name="x"/> Reject
              </button>
            </div>
            <button className="btn full" onClick={()=>setDecision("escalate")}>
              <Icon name="escalate"/> Escalate
            </button>
            {decision && (
              <div className="muted" style={{fontSize:12,textAlign:"center"}}>
                Recorded: <b style={{color:"var(--ink)"}}>{decision}</b>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function WorklistView({ onOpenCase }) {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");

  const cases = useMemo(()=>{
    let list = DATA.cases.slice();
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(c=>c.client.toLowerCase().includes(s)||c.id.toLowerCase().includes(s)||c.jurisdiction.toLowerCase().includes(s));
    }
    if (filter==="review") list = list.filter(c=>c.status==="Escalated"||c.status==="Pending review");
    if (filter==="high")   list = list.filter(c=>c.risk==="high");
    if (filter==="pass")   list = list.filter(c=>c.status==="Cleared");
    return list;
  },[filter,search]);

  const chips = [{v:"all",l:"All"},{v:"review",l:"Needs review"},{v:"high",l:"High risk"},{v:"pass",l:"Cleared"}];

  return (
    <>
      <div className="page-h" style={{marginBottom:16}}>
        <div>
          <div className="eyebrow">Worklist</div>
          <h1 className="page-title">KYC case queue</h1>
          <div className="page-sub">High Net Worth Individuals · {DATA.runAt}</div>
        </div>
      </div>

      <KpiStrip kpis={DATA.kpis}/>

      <div className="section-h" style={{marginTop:8}}>
        <h3>Active queue</h3>
        <div style={{display:"flex",alignItems:"center",gap:12}}>
          <div className="chips">
            {chips.map(c=>(
              <button key={c.v} className="chip" data-active={filter===c.v} onClick={()=>setFilter(c.v)}>{c.l}</button>
            ))}
          </div>
          <div className="search" style={{width:220}}>
            <Icon name="search"/>
            <input placeholder="Search clients, IDs…" value={search} onChange={e=>setSearch(e.target.value)}/>
          </div>
        </div>
      </div>

      <div className="card">
        <div style={{overflowX:"auto"}}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Client</th>
                <th style={{width:140}}>Risk</th>
                <th>Action needed</th>
                <th style={{width:120}}>Due</th>
              </tr>
            </thead>
            <tbody>
              {cases.map(c=>{
                const bc = c.status==="Escalated"?"b-bad":c.status==="Dual-approval"?"b-accent":c.status==="Cleared"?"b-ok":c.status==="Awaiting docs"?"b-warn":"b-mute";
                return (
                  <tr key={c.id} onClick={()=>onOpenCase(c)}>
                    <td>
                      <div className="cell-client">
                        <div className="ini">{c.ini}</div>
                        <div>
                          <b>{c.client}</b>
                          <small>{c.tier} · {c.jurisdiction}</small>
                        </div>
                      </div>
                    </td>
                    <td><RiskBar risk={c.risk} score={c.riskScore}/></td>
                    <td><span className={`badge ${bc}`}><span className="dot"/>{c.status}</span></td>
                    <td><span className={`sla ${c.sla.tone}`}>{c.sla.label}</span></td>
                  </tr>
                );
              })}
              {cases.length===0 && (
                <tr><td colSpan={4} style={{textAlign:"center",padding:"32px 0",color:"var(--ink-4)"}}>No cases match the current filter</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function App() {
  const [view, setView]      = useState("worklist");
  const [activeCase, setActiveCase] = useState(null);

  const openCase = (c) => { setActiveCase(c); setView("case"); };
  const goBack   = ()  => setView("worklist");

  return (
    <div style={{padding:"20px 24px",minHeight:"100%",background:"var(--bg-sunken)"}}>
      {view==="worklist" && <WorklistView onOpenCase={openCase}/>}
      {view==="case"     && <CasePanel c={activeCase} onBack={goBack}/>}
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App/>);
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{css}</style>
</head>
<body>
<div id="root"></div>
<script>window.__QUEUE_DATA__ = {data_json};</script>
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
<script type="text/babel" data-presets="react">
{react_code}
</script>
</body>
</html>"""


# ── Main render ────────────────────────────────────────────────────────────────

def render(user: Dict[str, Any], role: str, logger: Any) -> None:
    if not st.session_state.get("engines_initialized"):
        st.warning("No data loaded yet. Use Data & Documents to load customer files before running the queue.")
        _render_admin_tools(user, role, logger)
        return

    # ── Controls row: institution picker + run button ──────────────────────────
    institutions = _get_available_institutions()
    institution_labels = [label for _, label in institutions]
    configured = get_configured_institution()
    default_index = 0
    if configured and configured in [iid for iid, _ in institutions]:
        default_index = [iid for iid, _ in institutions].index(configured)

    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])
    with ctrl1:
        st.selectbox("Institution", institution_labels, index=default_index,
                     key="dashboard_institution_label", label_visibility="collapsed")
    with ctrl2:
        if st.button("Run queue", type="primary", use_container_width=True, key="dashboard_run_queue"):
            sel_label = st.session_state.get("dashboard_institution_label", institution_labels[default_index])
            sel_id = next((iid for iid, lbl in institutions if lbl == sel_label), "__none__")
            institution_id = None if sel_id == "__none__" else sel_id
            _run_dashboard_batch(user, logger, institution_id)
    with ctrl3:
        if st.session_state.get("batch_run_at"):
            st.caption("Last sync " + str(st.session_state.get("batch_run_at", "-"))
                       + "  ·  batch " + str(st.session_state.get("batch_id", "-")))

    if st.session_state.get("batch_results") is None:
        st.info("Run the queue to evaluate all customers and populate the dashboard.")
        _render_admin_tools(user, role, logger)
        return

    # ── Build data and render the design-faithful HTML component ──────────────
    batch_results = st.session_state.get("batch_results")
    customers_df  = st.session_state.get("customers_df")
    all_rows = _build_queue_rows(batch_results, customers_df, role)

    if not all_rows:
        st.info("No customers in the current queue run.")
        _render_admin_tools(user, role, logger)
        return

    component_data = _build_component_data(
        all_rows, batch_results,
        str(st.session_state.get("batch_id", "—")),
        str(st.session_state.get("batch_run_at", datetime.now().strftime("%a, %d %b %Y"))),
    )
    html = _build_dashboard_html(component_data)
    st_components.html(html, height=980, scrolling=True)

    # Admin-only tools at the bottom
    _render_admin_tools(user, role, logger)
