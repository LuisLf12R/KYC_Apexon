"""
app.py — KYC Compliance Platform
Apexon Case Study 02 | Full Platform Edition
"""

import streamlit as st
import pandas as pd
import json
import io
import os
import sys
import tempfile
import uuid
import zipfile
import hashlib
import base64
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import plotly.graph_objects as go
from src.dataframe_arrow_compat import coerce_expected_text_columns, make_arrow_compatible

load_dotenv()
st.set_page_config(
    page_title="KYC Compliance Platform",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global styles ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Tab list container */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    padding: 4px 0 0 0;
    border-bottom: 2px solid rgba(255,255,255,0.08);
}
/* Individual tab */
.stTabs [data-baseweb="tab"] {
    font-size: 15px;
    font-weight: 500;
    padding: 12px 24px;
    border-radius: 6px 6px 0 0;
    color: rgba(255,255,255,0.6);
    background: transparent;
    border: none;
    letter-spacing: 0.01em;
    transition: color 0.15s ease, background 0.15s ease;
}
/* Hover state */
.stTabs [data-baseweb="tab"]:hover {
    color: rgba(255,255,255,0.9);
    background: rgba(255,255,255,0.05);
}
/* Active tab */
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #ffffff;
    font-weight: 700;
    background: rgba(255,255,255,0.06);
}
/* Active tab underline indicator */
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #0072B2;
    height: 3px;
    border-radius: 2px 2px 0 0;
}
/* Tab panel content area */
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 24px;
}
</style>
""", unsafe_allow_html=True)


# ── Constants ─────────────────────────────────────────────────────────────────

INACTIVITY_WARNING_SEC = 13 * 60
INACTIVITY_TIMEOUT_SEC = 15 * 60
RULESET_VERSION = "kyc-ruleset-v1.0"
ACCEPTED_TYPES = ["csv", "xlsx", "xls", "json", "jsonl", "png", "jpg", "jpeg", "tiff", "bmp", "pdf"]
DATASET_OPTIONS = ["customers", "screenings", "id_verifications", "transactions", "documents", "beneficial_ownership"]
AUTO_DETECT = "Auto-detect (AI classifies)"
LOW_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_SLA_AMBER_DAYS = 3
DEFAULT_SLA_RED_DAYS = 7

KYC_SCHEMAS_HINT = {
    "customers": "customer_id, entity_type, jurisdiction, risk_rating, account_open_date, last_kyc_review_date, country_of_origin",
    "screenings": "customer_id, screening_date, screening_result, match_name, list_reference, hit_status",
    "id_verifications": "customer_id, document_type, document_number, issue_date, expiry_date, verification_date, document_status",
    "transactions": "customer_id, last_txn_date, txn_count, total_volume",
    "documents": "customer_id, document_type, issue_date, expiry_date, document_category",
    "beneficial_ownership": "customer_id, ubo_name, ownership_percentage, nationality, date_identified",
}

FALSE_POSITIVE_CODES = [
    "OCR Error — Extraction Misread",
    "Name Match Cleared — Verified Different Person",
    "Address Variant Accepted — Same Location Different Format",
    "Acceptable Risk Exception — Approved by Policy",
    "Duplicate Record — Same Customer Different ID",
    "Expired Document — Renewal Confirmed",
    "Other — See Notes",
]

# Okabe-Ito colorblind-safe palette
COLORS = {
    "compliant":     "#009E73",
    "minor":         "#E69F00",
    "non_compliant": "#D55E00",
    "blue":          "#0072B2",
    "gray":          "#999999",
}

DISPOSITION_CONFIG = {
    "REJECT":          {"label": "Reject",           "color": "#D55E00", "icon": "🚫"},
    "REVIEW":          {"label": "Review Required",  "color": "#E69F00", "icon": "⚠️"},
    "PASS_WITH_NOTES": {"label": "Pass with Notes",  "color": "#0072B2", "icon": "📋"},
    "PASS":            {"label": "Pass",             "color": "#009E73", "icon": "✅"},
}

def disposition_badge(disposition: str) -> str:
    """Return an HTML badge for a disposition value."""
    cfg = DISPOSITION_CONFIG.get(disposition, {"label": disposition, "color": "#999999", "icon": "?"})
    return (
        f"<span style='background:{cfg['color']};color:white;padding:3px 10px;"
        f"border-radius:4px;font-weight:bold;font-size:13px'>"
        f"{cfg['icon']} {cfg['label']}</span>"
    )

def show_disposition(disposition: str):
    """Render the appropriate Streamlit status element for a disposition."""
    cfg = DISPOSITION_CONFIG.get(disposition, {"label": disposition, "color": "#999", "icon": "?"})
    label = f"{cfg['icon']} {cfg['label']}"
    if disposition == "REJECT":
        st.error(label)
    elif disposition == "REVIEW":
        st.warning(label)
    elif disposition == "PASS_WITH_NOTES":
        st.info(label)
    else:
        st.success(label)

# ── API keys ──────────────────────────────────────────────────────────────────

@st.cache_resource
def init_api_keys():
    try:
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        if not claude_key:
            return False, "ANTHROPIC_API_KEY not configured"
        os.environ["ANTHROPIC_API_KEY"] = claude_key
        google_key_json = None
        google_path = os.getenv("GOOGLE_VISION_JSON_PATH")
        if google_path and Path(google_path).exists():
            with open(google_path) as f:
                google_key_json = json.load(f)
        if not google_key_json:
            b64 = os.getenv("GOOGLE_VISION_JSON_BASE64")
            if b64:
                google_key_json = json.loads(base64.b64decode(b64).decode("utf-8"))
        if not google_key_json:
            raw = os.getenv("GOOGLE_VISION_JSON")
            if raw:
                google_key_json = json.loads(raw)
        if not google_key_json:
            return False, "Google Vision API key not configured"
        creds_path = Path(tempfile.gettempdir()) / ".kyc_google_creds.json"
        with open(creds_path, "w") as f:
            json.dump(google_key_json, f)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)
        return True, "OK"
    except Exception as e:
        return False, str(e)

keys_ok, keys_msg = init_api_keys()
if not keys_ok:
    st.error(f"Configuration Error: {keys_msg}")
    st.stop()

# One-time cache purge: scripts generated under prior canonical schemas
# produce invalid output and must be regenerated.
if "_schema_cache_purged" not in st.session_state:
    try:
        from src.schema_harmonizer import SchemaHarmonizer
        SchemaHarmonizer().purge_stale_cache()
    except Exception:
        pass
    st.session_state._schema_cache_purged = True

# ── Prompt registry ───────────────────────────────────────────────────────────

@st.cache_resource
def load_prompt_registry():
    prompts = {}
    try:
        reg = Path.cwd() / "prompts" / "registry.json"
        if reg.exists():
            with open(reg) as f:
                registry = json.load(f)
            for entry in registry.get("prompts", []):
                if entry.get("active"):
                    pf = Path.cwd() / "prompts" / entry["file"]
                    if pf.exists():
                        with open(pf) as f:
                            prompts[entry["id"]] = json.load(f)
    except Exception:
        pass
    return prompts

PROMPTS = load_prompt_registry()

def get_prompt(pid):
    return PROMPTS.get(pid, {})

# ── User management ───────────────────────────────────────────────────────────

@st.cache_data
def load_users():
    try:
        p = Path.cwd() / "users.json"
        if p.exists():
            with open(p) as f:
                data = json.load(f)
            return {u["username"]: u for u in data.get("users", []) if u.get("active", True)}
    except Exception:
        pass
    return {
        "admin":    {"user_id": "fb_admin",   "username": "admin",    "password": "admin123",   "role": "Admin",   "full_name": "Administrator"},
        "manager":  {"user_id": "fb_mgr",     "username": "manager",  "password": "mgr123",     "role": "Manager", "full_name": "Compliance Manager"},
        "analyst1": {"user_id": "fb_a1",      "username": "analyst1", "password": "analyst123", "role": "Analyst", "full_name": "KYC Analyst One"},
        "analyst2": {"user_id": "fb_a2",      "username": "analyst2", "password": "analyst456", "role": "Analyst", "full_name": "KYC Analyst Two"},
        "viewer":   {"user_id": "fb_viewer",  "username": "viewer",   "password": "viewer123",  "role": "Viewer",  "full_name": "Read Only Reviewer"},
    }

def authenticate(username, password):
    users = load_users()
    u = users.get(username.strip().lower())
    if u and u.get("password") == password:
        return u
    return None

# ── Session state defaults ────────────────────────────────────────────────────

_DEFAULTS = {
    "authenticated": False, "current_user": None, "audit_logger": None,
    "last_activity": None, "timeout_warning_logged": False, "pii_masked": True,
    "kyc_engine": None, "engines_initialized": False, "customers_df": None,
    "data_dir": None, "batch_results": None, "batch_id": None, "batch_run_at": None,
    "customer_history": {},
    "data_source_label": None,
    "case_sla_amber_days": DEFAULT_SLA_AMBER_DAYS,
    "case_sla_red_days": DEFAULT_SLA_RED_DAYS,
    "latest_export_package": None,
    "provenance_store": None,
    "dirty_customers": set(),
    "ocr_analysis_cache": {},
    "latest_discrepancy_report": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Audit helpers ─────────────────────────────────────────────────────────────

def get_logger():
    return st.session_state.get("audit_logger")

def log(action_type, details=None, customer_id=None, batch_id=None, snapshot=None, prompt_id=None):
    lg = get_logger()
    if lg:
        lg.log(action_type, details=details, customer_id=customer_id,
               batch_id=batch_id, snapshot=snapshot, prompt_id=prompt_id)

def touch():
    st.session_state.last_activity = datetime.now(timezone.utc)


def _ensure_runtime_action_types():
    """Allow app-level workflow actions without editing audit_logger.py."""
    try:
        sys.path.insert(0, str(Path.cwd() / "src"))
        from audit_logger import ACTION_TYPES
        ACTION_TYPES.setdefault("CASE_CLOSED", "Manager/Admin closed a customer case")
    except Exception:
        pass


def _get_provenance_store():
    if st.session_state.provenance_store is None:
        sys.path.insert(0, str(Path.cwd() / "src"))
        from data_provenance import CustomerProvenance
        st.session_state.provenance_store = CustomerProvenance()
    return st.session_state.provenance_store


def _format_conf_pct(conf):
    if conf is None or pd.isna(conf):
        return ""
    return f"{int(round(float(conf) * 100))}%"


def _seed_structured_provenance():
    """Seed user-provided structured fields into provenance once."""
    if not st.session_state.engines_initialized:
        return
    prov = _get_provenance_store()
    engine = st.session_state.kyc_engine
    if engine is None or engine.customers is None or len(engine.customers) == 0:
        return

    datasets = [engine.customers, engine.id_verifications, engine.screenings, engine.transactions, engine.beneficial_owners]
    for df in datasets:
        if df is None or len(df) == 0 or "customer_id" not in df.columns:
            continue
        for _, row in df.iterrows():
            cid = str(row.get("customer_id", "")).strip()
            if not cid:
                continue
            for field in df.columns:
                if field == "customer_id":
                    continue
                val = row.get(field)
                if pd.isna(val) or str(val).strip() == "":
                    continue
                if not prov.get_field_history(cid, field):
                    prov.set_field(cid, field, val, source="User-Provided")


def _collect_discrepancy_report():
    prov = _get_provenance_store()
    rows = []
    customer_ids = prov.get_customer_ids()
    for cid in customer_ids:
        disc = prov.detect_discrepancies(cid)
        if not disc:
            continue
        fields = []
        for d in disc:
            field = d["field_name"]
            fields.append(field)
            rows.append({
                "customer_id": cid,
                "field": field,
                "values_by_source": json.dumps(d["values_by_source"], default=str),
            })
        log("FLAG_RAISED", customer_id=cid, details={"reason": "data_discrepancy", "fields": sorted(set(fields))})
    return rows


def _customer_in_engine(customer_id: str) -> bool:
    if not st.session_state.engines_initialized or st.session_state.customers_df is None:
        return False
    cdf = st.session_state.customers_df
    if "customer_id" not in cdf.columns:
        return False
    return str(customer_id) in set(cdf["customer_id"].astype(str).tolist())


def _record_ocr_analysis_provenance(customer_id: str, analysis: dict, filename: str):
    if not customer_id:
        return []
    prov = _get_provenance_store()
    written = []
    for k, v in analysis.items():
        if k.endswith("_citation") or k.endswith("_confidence") or k in ("meta", "compliance_flags", "risk_indicators", "discrepancies", "extraction_summary"):
            continue
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        conf = analysis.get(f"{k}_confidence")
        prov.set_field(customer_id, k, v, source="OCR-Extracted", source_file=filename, confidence=conf)
        written.append({"field": k, "value": v, "confidence": conf})
    return written


def _update_single_customer_records(customer_id: str, doc_type: str, analysis: dict):
    engine = st.session_state.kyc_engine
    updated_fields = []
    cid = str(customer_id)
    now_date = datetime.now(timezone.utc).date().isoformat()

    def _upsert(df, values: dict):
        nonlocal updated_fields
        if df is None:
            return
        for col in values.keys():
            if col not in df.columns:
                df[col] = None
        match_idx = df.index[df["customer_id"].astype(str) == cid].tolist() if "customer_id" in df.columns else []
        if match_idx:
            idx = match_idx[0]
            for col, val in values.items():
                if val is not None and str(val).strip() != "":
                    df.at[idx, col] = val
                    updated_fields.append(col)
        else:
            row = {"customer_id": cid}
            row.update({k: v for k, v in values.items() if v is not None and str(v).strip() != ""})
            df.loc[len(df)] = row
            updated_fields.extend(list(row.keys()))

    identity_values = {
        "document_type": "IDENTITY_DOCUMENT",
        "document_number": analysis.get("document_number"),
        "issue_date": analysis.get("issue_date"),
        "expiry_date": analysis.get("expiry_date"),
        "verification_date": now_date,
        "document_status": "VERIFIED",
    }
    address_values = {
        "jurisdiction": analysis.get("address"),
        "country_of_origin": analysis.get("nationality"),
    }

    if "identity" in doc_type.lower() or "passport" in doc_type.lower():
        _upsert(engine.id_verifications, identity_values)
    elif "proof of address" in doc_type.lower():
        _upsert(engine.customers, address_values)
    else:
        _upsert(engine.id_verifications, identity_values)
        _upsert(engine.customers, address_values)

    if engine.customers is not None and "customer_id" in engine.customers.columns:
        st.session_state.customers_df = engine.customers.copy()
    return sorted(set(updated_fields))


def _get_provenance_table(customer_id: str):
    prov = _get_provenance_store()
    rows = []
    engine = st.session_state.kyc_engine
    base_fields = {}
    if engine and engine.customers is not None and "customer_id" in engine.customers.columns:
        match = engine.customers[engine.customers["customer_id"].astype(str) == str(customer_id)]
        if not match.empty:
            base_fields = match.iloc[0].to_dict()
    latest = prov.get_all_fields(customer_id)
    all_fields = sorted(set(base_fields.keys()) | set(latest.keys()))
    for field in all_fields:
        tag = latest.get(field)
        if tag:
            rows.append({
                "Field": field,
                "Current Value": tag.value,
                "Source": tag.source or "User-Provided",
                "Source File": tag.source_file or "",
                "Confidence": _format_conf_pct(tag.confidence),
                "Last Updated": tag.timestamp,
            })
        else:
            val = base_fields.get(field, "")
            if pd.isna(val):
                val = ""
            rows.append({
                "Field": field,
                "Current Value": val,
                "Source": "User-Provided",
                "Source File": "",
                "Confidence": "",
                "Last Updated": "",
            })
    return rows


def _parse_iso(ts: str):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _format_ago(ts: str) -> str:
    dt = _parse_iso(ts)
    if not dt:
        return "unknown"
    delta = datetime.now(timezone.utc) - dt
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hrs = mins // 60
    if hrs < 24:
        return f"{hrs}h ago"
    return f"{hrs // 24}d ago"


def _get_current_customer_state(customer_id: str):
    disposition, score = "N/A", "N/A"
    history = st.session_state.customer_history.get(customer_id, [])
    if history:
        disposition = history[-1].get("disposition", disposition)
        score = history[-1].get("overall_score", score)
    elif st.session_state.batch_results is not None:
        rdf = st.session_state.batch_results
        row = rdf[rdf["customer_id"].astype(str) == str(customer_id)]
        if not row.empty:
            disposition = row.iloc[0].get("disposition", disposition)
            score = row.iloc[0].get("overall_score", score)
    return disposition, score


def _get_pending_clear_approvals(logger):
    if not logger:
        return []
    pending = {}
    for e in logger.events:
        cid = e.get("customer_id")
        action = e.get("action_type")
        if not cid:
            continue
        if action == "CLEAR_PROPOSED":
            pending[cid] = e
        elif action in ("CLEAR_APPROVED", "CLEAR_REJECTED"):
            pending.pop(cid, None)
    rows = []
    for cid, e in pending.items():
        details = e.get("details", {})
        disposition, score = _get_current_customer_state(cid)
        rows.append({
            "customer_id": cid,
            "proposed_by": e.get("username", ""),
            "reason_code": details.get("reason_code", ""),
            "note": details.get("note", ""),
            "proposed_at": e.get("timestamp"),
            "proposed_at_ago": _format_ago(e.get("timestamp")),
            "disposition": disposition,
            "score": score,
            "event_id": e.get("event_id"),
        })
    return sorted(rows, key=lambda x: x.get("proposed_at", ""))


def _sla_badge(case_opened_at: str, case_status: str) -> str:
    if case_status == "Closed":
        return "🟢 On time"
    opened = _parse_iso(case_opened_at)
    if not opened:
        return "⚪ Unknown"
    age_days = (datetime.now(timezone.utc) - opened).total_seconds() / 86400
    amber = st.session_state.case_sla_amber_days
    red = st.session_state.case_sla_red_days
    if age_days >= red:
        return f"🔴 {int(age_days)}d open"
    if age_days >= amber:
        return f"🟠 {int(age_days)}d open"
    return f"🟢 {int(age_days)}d open"


def _build_cases(logger):
    if not logger:
        return []
    events = logger.events
    trigger_actions = {"FLAG_RAISED", "CLEAR_PROPOSED", "CUSTOMER_ESCALATED", "CLEAR_APPROVED", "CLEAR_REJECTED"}
    close_actions = {"CASE_CLOSED"}
    by_customer = {}
    for e in events:
        cid = e.get("customer_id")
        if not cid:
            continue
        by_customer.setdefault(cid, []).append(e)

    cases = []
    for cid, history in by_customer.items():
        history = sorted(history, key=lambda x: x.get("timestamp", ""))
        has_trigger = False
        opened_event = None
        for e in history:
            action = e.get("action_type")
            if action in trigger_actions:
                has_trigger = True
                opened_event = opened_event or e
            if action == "CUSTOMER_VIEW":
                disp = (e.get("snapshot") or {}).get("disposition")
                if disp in ("REJECT", "REVIEW"):
                    has_trigger = True
                    opened_event = opened_event or e
        if not has_trigger:
            continue

        latest = history[-1]
        disposition, score = _get_current_customer_state(cid)
        if disposition == "N/A":
            for e in reversed(history):
                disp = (e.get("snapshot") or {}).get("disposition")
                if disp:
                    disposition = disp
                    score = (e.get("snapshot") or {}).get("overall_score", score)
                    break
        has_closed = any(e.get("action_type") in close_actions for e in history)
        has_pending = any(e.get("action_type") == "CLEAR_PROPOSED" for e in history) and not any(
            e.get("action_type") in ("CLEAR_APPROVED", "CLEAR_REJECTED") for e in history
        )
        case_status = "Closed" if has_closed else ("Pending Approval" if has_pending else "Open")
        opened_at = opened_event.get("timestamp") if opened_event else latest.get("timestamp")
        case_id = f"CASE-{cid}-{(_parse_iso(opened_at) or datetime.now(timezone.utc)).strftime('%Y%m%d')}"

        case_rows = []
        for e in history:
            case_rows.append({
                "timestamp": e.get("timestamp"),
                "action": e.get("action_type"),
                "user": e.get("username"),
                "role": e.get("role"),
                "details": json.dumps(e.get("details", {}), default=str),
            })

        cases.append({
            "case_id": case_id,
            "customer_id": cid,
            "current_disposition": disposition,
            "current_score": score,
            "case_status": case_status,
            "opened_by": opened_event.get("username") if opened_event else latest.get("username"),
            "opened_at": opened_at,
            "case_history": case_rows,
            "sla_badge": _sla_badge(opened_at, case_status),
        })
    return sorted(cases, key=lambda x: x["opened_at"], reverse=True)


def _build_export_package(logger, user):
    session_id = logger.session_id
    batch_id = st.session_state.batch_id or "no_batch"
    export_ts = datetime.now(timezone.utc)
    export_ts_str = export_ts.strftime("%Y%m%d_%H%M%S")

    files = {}
    audit_payload = logger.finalize()
    audit_name = f"audit_log_{session_id}.json"
    files[audit_name] = json.dumps(audit_payload, indent=2, default=str)

    batch_name = f"batch_results_{batch_id}.csv"
    flagged_name = f"flagged_customers_{batch_id}.csv"
    if st.session_state.batch_results is not None:
        rdf = st.session_state.batch_results.copy()
        batch_buf = io.StringIO()
        rdf.to_csv(batch_buf, index=False)
        files[batch_name] = batch_buf.getvalue()
        flagged = rdf[rdf["disposition"].isin(["REJECT", "REVIEW"])].copy()
        flag_buf = io.StringIO()
        if flagged.empty:
            flag_buf.write("note\nNo REJECT or REVIEW customers in latest batch.\n")
        else:
            include_cols = [c for c in ["customer_id", "disposition", "overall_score", "rationale"] if c in flagged.columns]
            flagged[include_cols].to_csv(flag_buf, index=False)
        files[flagged_name] = flag_buf.getvalue()
        total_customers = len(rdf)
    else:
        files[batch_name] = "note\nNo batch evaluation was run in this session.\n"
        files[flagged_name] = "note\nNo batch evaluation was run in this session.\n"
        total_customers = 0

    metadata = {
        "session_id": session_id,
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
        "session_start_time": logger.session_start,
        "export_timestamp": export_ts.isoformat(),
        "ruleset_version_active": RULESET_VERSION,
        "prompt_versions_active": {pid: p.get("version", "unknown") for pid, p in PROMPTS.items()},
        "total_audit_events": logger.event_count(),
        "total_customers_evaluated_in_batch": total_customers,
    }
    files["session_metadata.json"] = json.dumps(metadata, indent=2, default=str)

    verification_hash = hashlib.sha256(
        (
            str(audit_payload.get("previous_session_hash", ""))
            + json.dumps(audit_payload.get("events", []), sort_keys=True, default=str)
        ).encode("utf-8")
    ).hexdigest()
    files["README.txt"] = (
        "KYC Compliance Export Package\n\n"
        f"- {audit_name}: Finalized session audit log with appended session_hash.\n"
        f"- {batch_name}: Latest batch results (or note when no batch exists).\n"
        f"- {flagged_name}: Batch subset where disposition is REJECT or REVIEW.\n"
        "- session_metadata.json: Session and export metadata.\n"
        "- README.txt: Package guidance.\n\n"
        "Audit verification:\n"
        "Recompute SHA-256 of (previous_session_hash + sorted JSON events) and compare to session_hash.\n"
        f"Computed hash for this export: {verification_hash}\n"
    )

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content if isinstance(content, str) else str(content))
    zbuf.seek(0)

    manifest = [{"file": name, "size_bytes": len(content.encode("utf-8"))} for name, content in files.items()]
    zip_name = f"kyc_export_{user['username']}_{export_ts_str}.zip"
    return zbuf.getvalue(), zip_name, manifest



# ── Timeout ───────────────────────────────────────────────────────────────────

def check_timeout():
    if not st.session_state.authenticated:
        return False
    last = st.session_state.last_activity
    if last is None:
        return True
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    if elapsed >= INACTIVITY_TIMEOUT_SEC:
        log("SESSION_EXPIRED", details={"elapsed_seconds": int(elapsed),
                                         "reason": "15-min FFIEC/PSD2 inactivity limit"})
        _force_logout()
        return False
    if elapsed >= INACTIVITY_WARNING_SEC and not st.session_state.timeout_warning_logged:
        log("SESSION_TIMEOUT_WARNING", details={"elapsed_seconds": int(elapsed),
             "note": "Logged so auditors can understand re-login patterns within short time windows."})
        st.session_state.timeout_warning_logged = True
    return True

def _force_logout():
    lg = get_logger()
    final = lg.export_json() if lg else None
    for k in list(st.session_state.keys()):
        if k != "_final_log":
            del st.session_state[k]
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v
    if final:
        st.session_state["_final_log"] = final

# ── PII masking ───────────────────────────────────────────────────────────────

def can_unmask():
    u = st.session_state.current_user
    return u and u.get("role") in ("Manager", "Admin")

def mask(value, field_type="default"):
    if not st.session_state.pii_masked or can_unmask():
        return str(value) if value is not None else "N/A"
    masks = {
        "ssn": "***-**-****", "dob": "**/**/****",
        "account": f"****{str(value)[-4:]}" if value and len(str(value)) >= 4 else "****",
        "name": f"{str(value)[0]}***" if value else "***",
        "address": "[MASKED]", "default": "[MASKED]",
    }
    return masks.get(field_type, masks["default"])

# ── Engine loader ─────────────────────────────────────────────────────────────

def load_engine(data_dir):
    try:
        sys.path.insert(0, str(Path.cwd() / "src"))
        from kyc_engine import KYCComplianceEngine
        engine = KYCComplianceEngine(data_clean_dir=data_dir)
        return engine, engine.customers
    except Exception as e:
        return None, str(e)

# ── Data cleaning ─────────────────────────────────────────────────────────────

def clean_dataframe(df, dataset_type):
    df.columns = [c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]
    ALIASES = {
        "customers": {"id": "customer_id", "cust_id": "customer_id", "type": "entity_type",
                      "country": "jurisdiction", "risk": "risk_rating", "risk_level": "risk_rating",
                      "open_date": "account_open_date", "kyc_date": "last_kyc_review_date"},
        "screenings": {"id": "customer_id", "date": "screening_date", "result": "screening_result",
                       "match": "match_name", "list": "list_reference", "hit": "hit_status"},
        "id_verifications": {"id": "customer_id", "doc_type": "document_type", "issue": "issue_date",
                              "expiry": "expiry_date", "verify_date": "verification_date",
                              "status": "document_status"},
        "transactions": {"id": "customer_id", "last_date": "last_txn_date",
                         "count": "txn_count", "volume": "total_volume"},
        "documents": {"id": "customer_id", "doc_type": "document_type",
                      "issue": "issue_date", "expiry": "expiry_date"},
        "beneficial_ownership": {"id": "customer_id", "name": "ubo_name",
                                  "ownership": "ownership_percentage", "date": "date_identified"},
    }
    df = df.rename(columns=ALIASES.get(dataset_type, {}))
    df = coerce_expected_text_columns(df, dataset_type=dataset_type)
    for col in df.columns:
        if any(k in col for k in ["date", "expiry", "expiration"]):
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in df.select_dtypes(include="object").columns:
        series = df[col]
        if isinstance(series, pd.DataFrame):
            # Duplicate column name — keep first occurrence
            series = series.iloc[:, 0]
            df = df.loc[:, ~df.columns.duplicated()]
        try:
            df[col] = series.str.strip()
        except AttributeError:
            # Column contains non-string values (lists, dicts); leave as-is
            pass
    for col in ["screening_result", "hit_status", "document_status", "risk_rating"]:
        if col in df.columns:
            series = df[col]
            if isinstance(series, pd.DataFrame):
                series = series.iloc[:, 0]
                df = df.loc[:, ~df.columns.duplicated()]
            try:
                df[col] = series.str.upper()
            except AttributeError:
                pass
    return df


def st_dataframe_safe(data, **kwargs):
    """Render DataFrames through an Arrow-safe normalization layer."""
    if isinstance(data, pd.DataFrame):
        data = make_arrow_compatible(data)
    st.dataframe(data, **kwargs)

def save_to_temp(dataframes):
    tmp = Path(tempfile.gettempdir()) / "kyc_data_clean"
    tmp.mkdir(parents=True, exist_ok=True)
    name_map = {
        "customers": "customers_clean.csv", "screenings": "screenings_clean.csv",
        "id_verifications": "id_verifications_clean.csv", "transactions": "transactions_clean.csv",
        "documents": "documents_clean.csv", "beneficial_ownership": "beneficial_ownership_clean.csv",
    }
    for key, df in dataframes.items():
        if isinstance(df, pd.DataFrame) and not df.empty:
            df.to_csv(tmp / name_map.get(key, f"{key}_clean.csv"), index=False)
    return tmp

# ── Ingestion pipeline ────────────────────────────────────────────────────────

def read_structured(file_obj, filename):
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return pd.read_csv(file_obj)
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(file_obj)
    elif ext == ".json":
        content = json.load(file_obj)
        if isinstance(content, list):
            return pd.DataFrame(content)
        for key in ["data", "records", "customers", "results"]:
            if key in content and isinstance(content[key], list):
                return pd.DataFrame(content[key])
        return pd.DataFrame([content])
    elif ext == ".jsonl":
        return pd.read_json(file_obj, lines=True)
    raise ValueError(f"Unsupported: {ext}")

def run_ocr(file_bytes, filename):
    from google.cloud import vision as gv
    client = gv.ImageAnnotatorClient()
    if Path(filename).suffix.lower() == ".pdf":
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(io.BytesIO(file_bytes))
            if text and len(text.strip()) > 50:
                return text
        except Exception:
            pass
    resp = client.document_text_detection(image=gv.Image(content=file_bytes))
    if resp.error.message:
        raise RuntimeError(f"Vision API: {resp.error.message}")
    return resp.full_text_annotation.text if resp.full_text_annotation else ""

def llm_structure(raw_text, dataset_type, filename):
    import anthropic as ac
    cfg = get_prompt("kyc-structuring-v1.0")
    system = cfg.get("system", "Extract KYC records and return a JSON array.")
    tmpl = cfg.get("user_template", "{ocr_text}")
    user = tmpl.format(dataset_type=dataset_type,
                       schema_hint=KYC_SCHEMAS_HINT.get(dataset_type, ""),
                       filename=filename, ocr_text=raw_text[:6000])
    mcfg = cfg.get("model_settings", {})
    client = ac.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=mcfg.get("model", "claude-opus-4-20250514"),
        max_tokens=mcfg.get("max_tokens", 4000),
        system=system, messages=[{"role": "user", "content": user}]
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    records = json.loads(raw)
    if isinstance(records, dict):
        records = [records]
    return pd.DataFrame(records)

def autodetect(sample, filename):
    import anthropic as ac
    cfg = get_prompt("autodetect-v1.0")
    system = cfg.get("system", f"Classify into: {', '.join(DATASET_OPTIONS)}. Return type only.")
    tmpl = cfg.get("user_template", "Filename: {filename}\n\nSample:\n{sample}")
    mcfg = cfg.get("model_settings", {})
    client = ac.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=mcfg.get("model", "claude-opus-4-20250514"),
        max_tokens=mcfg.get("max_tokens", 50),
        system=system,
        messages=[{"role": "user", "content": tmpl.format(filename=filename, sample=sample[:1500])}]
    )
    detected = resp.content[0].text.strip().lower().replace(" ", "_")
    return detected if detected in DATASET_OPTIONS else "customers"

def process_file(file_obj, filename, dataset_type):
    ext = Path(filename).suffix.lower()
    if ext in {".csv", ".xlsx", ".xls", ".json", ".jsonl"}:
        df = read_structured(file_obj, filename)
        if dataset_type == AUTO_DETECT:
            dataset_type = autodetect(df.head(3).to_string(), filename)
            log("AUTODETECT_RUN", prompt_id="autodetect-v1.0",
                details={"filename": filename, "detected": dataset_type})
        # Harmonize to canonical schema BEFORE clean_dataframe.
        # HarmonizationRejected propagates; generic errors log and fall back.
        from src.schema_harmonizer import SchemaHarmonizer, HarmonizationRejected
        harmonizer = SchemaHarmonizer()
        if dataset_type in harmonizer.SUPPORTED_TARGETS:
            df_before_cols = list(df.columns)
            try:
                df, harmonize_meta = harmonizer.normalize(df, dataset_type)
                log(
                    "SCHEMA_HARMONIZED",
                    details={
                        "filename": filename,
                        "target_type": dataset_type,
                        "source": harmonize_meta["source"],
                        "script_id": harmonize_meta["script_id"],
                        "input_columns": df_before_cols,
                        "rows_in": harmonize_meta["row_count_in"],
                        "rows_out": harmonize_meta["row_count_out"],
                        "critical_coverage": harmonize_meta["critical_coverage"],
                        "nice_coverage": harmonize_meta["nice_coverage"],
                    },
                )
            except HarmonizationRejected as rej:
                log(
                    "SCHEMA_HARMONIZE_REJECTED",
                    details={
                        "filename": filename,
                        "target_type": dataset_type,
                        "report": rej.report,
                    },
                )
                # Re-raise so caller can render a dedicated rejection UI
                raise
            except Exception as e:
                log(
                    "SCHEMA_HARMONIZE_FAILED",
                    details={
                        "filename": filename,
                        "target_type": dataset_type,
                        "error": str(e),
                    },
                )
                # Generic failure: continue with raw DataFrame

        df = clean_dataframe(df, dataset_type)
        return df, "direct", dataset_type, f"Loaded {len(df)} rows"
    else:
        file_bytes = file_obj.read()
        log("OCR_RUN", prompt_id="kyc-analysis-v1.0",
            details={"filename": filename, "bytes": len(file_bytes)})
        raw_text = run_ocr(file_bytes, filename)
        if not raw_text or len(raw_text.strip()) < 20:
            raise ValueError("No usable text from OCR.")
        if dataset_type == AUTO_DETECT:
            dataset_type = autodetect(raw_text, filename)
            log("AUTODETECT_RUN", prompt_id="autodetect-v1.0",
                details={"filename": filename, "detected": dataset_type})
        log("LLM_CALL", prompt_id="kyc-structuring-v1.0",
            details={"filename": filename, "dataset_type": dataset_type, "chars": len(raw_text)})
        df = llm_structure(raw_text, dataset_type, filename)
        df = clean_dataframe(df, dataset_type)
        return df, "ocr+llm", dataset_type, f"Extracted {len(df)} records"


def _extract_json_from_response(raw: str) -> dict:
    """
    Robustly extract a JSON object from an LLM response string.
    Handles: leading/trailing whitespace, markdown code fences,
    partial responses starting mid-object, and extra text before/after.
    """
    if not raw:
        raise ValueError("Empty response from LLM")

    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # If it doesn't start with {, try to find the first { in the text
    if not text.startswith("{"):
        start = text.find("{")
        if start != -1:
            text = text[start:]
        else:
            # Try wrapping loose key-value content in braces
            text = "{" + text.strip().rstrip(",") + "}"

    # Find the last } to trim any trailing content
    end = text.rfind("}")
    if end != -1:
        text = text[:end + 1]

    return json.loads(text)


# ╔══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ╚══════════════════════════════════════════════════════════════════════════════

def render_login():
    if st.session_state.get("_final_log"):
        st.warning("Session expired. Download your audit log before closing.")
        st.download_button("Download Audit Log",
                           st.session_state["_final_log"],
                           file_name=f"audit_expired_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                           mime="application/json")
        st.divider()

    _, col, _ = st.columns([2, 1, 2])
    with col:
        st.markdown("## 🏦 KYC Compliance Platform")
        st.divider()
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Sign In", type="primary", use_container_width=True):
            user = authenticate(username, password)
            if user:
                sys.path.insert(0, str(Path.cwd() / "src"))
                from audit_logger import AuditLogger
                logger = AuditLogger(user)
                st.session_state.authenticated = True
                st.session_state.current_user = user
                st.session_state.audit_logger = logger
                st.session_state.last_activity = datetime.now(timezone.utc)
                st.session_state.timeout_warning_logged = False
                st.session_state.pii_masked = True
                logger.log("LOGIN", details={"username": user["username"],
                                              "role": user["role"], "pii_masked_on_login": True})
                _try_autoload_engine()
                st.rerun()
            else:
                st.error("Invalid credentials.")
        st.caption("Sessions expire after 15 minutes of inactivity (FFIEC / PSD2 standard).")


def _try_autoload_engine():
    """
    On login, try to load data in this order:
    1. Default 'Data Clean/' folder (committed to repo)
    2. Temp dir from a previous session this deployment (kyc_data_clean/)
    Silently skips if neither exists or neither has customers.
    """
    default_dir = Path.cwd() / "Data Clean"
    if default_dir.exists():
        engine, customers = load_engine(default_dir)
        if engine is not None and customers is not None and len(customers) > 0:
            st.session_state.kyc_engine = engine
            st.session_state.customers_df = customers
            st.session_state.engines_initialized = True
            st.session_state.data_dir = default_dir
            st.session_state.data_source_label = "Data Clean/ (default)"
            _seed_structured_provenance()
            return

    tmp_dir = Path(tempfile.gettempdir()) / "kyc_data_clean"
    if tmp_dir.exists() and any(tmp_dir.glob("*.csv")):
        engine, customers = load_engine(tmp_dir)
        if engine is not None and customers is not None and len(customers) > 0:
            st.session_state.kyc_engine = engine
            st.session_state.customers_df = customers
            st.session_state.engines_initialized = True
            st.session_state.data_dir = tmp_dir
            st.session_state.data_source_label = "Previously cleaned data (auto-loaded)"
            _seed_structured_provenance()


# ╔══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ╚══════════════════════════════════════════════════════════════════════════════

def render_main():
    user = st.session_state.current_user
    role = user["role"]
    logger = get_logger()
    _ensure_runtime_action_types()
    _get_provenance_store()
    _seed_structured_provenance()

    # Inactivity warning banner (shown on next interaction after 13 min)
    if st.session_state.timeout_warning_logged:
        elapsed = (datetime.now(timezone.utc) - st.session_state.last_activity).total_seconds()
        remaining = max(0, INACTIVITY_TIMEOUT_SEC - elapsed)
        st.warning(
            f"Session expires in {int(remaining // 60)}m {int(remaining % 60)}s due to inactivity. "
            "Click anywhere to stay logged in. This event is logged.",
            icon="⚠️"
        )

    # Top bar
    c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
    with c1:
        st.markdown("### 🏦 KYC Compliance Platform")
    with c2:
        elapsed_min = 0
        if st.session_state.last_activity:
            elapsed_min = int((datetime.now(timezone.utc) - st.session_state.last_activity).total_seconds() // 60)
        st.markdown(f"**{user['full_name']}** · {role}  \n"
                    f"<span style='color:gray;font-size:12px'>{elapsed_min}m elapsed</span>",
                    unsafe_allow_html=True)
    with c3:
        if can_unmask():
            new_state = st.toggle("Mask PII", value=st.session_state.pii_masked, key="pii_toggle")
            if new_state != st.session_state.pii_masked:
                st.session_state.pii_masked = new_state
                log("PII_MASK_TOGGLED", details={"new_state": "masked" if new_state else "visible"})
                touch()
        else:
            st.markdown("<span style='color:gray;font-size:12px'>PII Masked</span>",
                        unsafe_allow_html=True)
    with c4:
        if st.button("Sign Out"):
            touch()
            log("LOGOUT", details={"voluntary": True})
            final = logger.export_json() if logger else None
            st.session_state["_final_log"] = final
            _force_logout()
            st.rerun()

    st.divider()

    # Status strip
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        if st.session_state.engines_initialized:
            n = len(st.session_state.customers_df)
            st.success(f"Engine Ready — {n:,} customers loaded")
        else:
            st.warning("No data — use Data Management")
    with s2:
        st.info(f"Ruleset: {RULESET_VERSION}")
    with s3:
        st.info(f"Audit events: {logger.event_count() if logger else 0}")
    with s4:
        st.info(f"Prompts loaded: {len(PROMPTS)}")

    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "Individual Evaluation", "Batch Results", "Data Management",
        "Document OCR & AI", "System Info", "Approval Queue", "Cases", "Audit Trail",
    ])

    # ════════════════════════════════════════════════════════
    # TAB 1: INDIVIDUAL EVALUATION
    # ════════════════════════════════════════════════════════
    with tab1:
        touch()
        if not st.session_state.engines_initialized:
            st.warning("No data loaded. Go to the Data Management tab to upload files.")
        else:
            st.markdown("### Search & Evaluate Customer")

            cid_input = st.text_input("Customer ID", placeholder="C00001",
                                       label_visibility="collapsed")
            eval_btn = st.button("Evaluate Customer", type="primary", use_container_width=True)

            if eval_btn and cid_input:
                cid = cid_input.strip().upper()
                touch()
                with st.spinner(f"Evaluating {cid}..."):
                    try:
                        result = st.session_state.kyc_engine.evaluate_customer(cid)
                        disposition = result.get("disposition", "REVIEW")
                        score = result.get("overall_score", 0)
                        rationale = result.get("rationale", "")
                        reject_rules = result.get("triggered_reject_rules", [])
                        review_rules = result.get("triggered_review_rules", [])
                        ruleset_ver = result.get("ruleset_version", "unknown")

                        log("CUSTOMER_VIEW", customer_id=cid,
                            details={"tab": "individual_evaluation",
                                     "ruleset_version": ruleset_ver},
                            snapshot={k: result.get(k) for k in [
                                "overall_score", "disposition",
                                "aml_screening_score", "identity_verification_score",
                                "account_activity_score", "proof_of_address_score",
                                "beneficial_ownership_score", "data_quality_score",
                            ]})

                        if disposition in ("REJECT", "REVIEW"):
                            log("FLAG_RAISED", customer_id=cid,
                                details={"disposition": disposition, "score": score,
                                         "triggered_rules": [r["rule_id"] for r in
                                                             reject_rules + review_rules]})

                        history_entry = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "evaluated_by": user["username"],
                            "overall_score": score,
                            "disposition": disposition,
                            "aml_screening_score": result.get("aml_screening_score", 0),
                            "identity_verification_score": result.get("identity_verification_score", 0),
                            "account_activity_score": result.get("account_activity_score", 0),
                            "proof_of_address_score": result.get("proof_of_address_score", 0),
                            "beneficial_ownership_score": result.get("beneficial_ownership_score", 0),
                            "data_quality_score": result.get("data_quality_score", 0),
                        }
                        if cid not in st.session_state.customer_history:
                            st.session_state.customer_history[cid] = []
                        st.session_state.customer_history[cid].append(history_entry)

                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Overall Score", f"{score}/100")
                        m2.metric("Customer ID", cid)
                        m3.metric("Ruleset", ruleset_ver)
                        m4.metric("Evaluations (session)",
                                  len(st.session_state.customer_history.get(cid, [])))

                        st.divider()

                        show_disposition(disposition)
                        st.markdown(f"**Rationale:** {rationale}")

                        if reject_rules:
                            st.markdown("**Hard Rejection Rules Triggered:**")
                            for r in reject_rules:
                                st.markdown(
                                    f"<div style='border-left:4px solid #D55E00;"
                                    f"padding:8px 12px;margin:4px 0;"
                                    f"background:rgba(213,94,0,0.08);border-radius:4px'>"
                                    f"<strong>{r['rule_id']} — {r['name']}</strong><br>"
                                    f"<span style='color:gray;font-size:13px'>{r['description']}</span><br>"
                                    f"<span style='color:gray;font-size:12px'>Policy: {r['policy_reference']}</span>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                        if review_rules:
                            st.markdown("**Review Rules Triggered:**")
                            for r in review_rules:
                                st.markdown(
                                    f"<div style='border-left:4px solid #E69F00;"
                                    f"padding:8px 12px;margin:4px 0;"
                                    f"background:rgba(230,159,0,0.08);border-radius:4px'>"
                                    f"<strong>{r['rule_id']} — {r['name']}</strong><br>"
                                    f"<span style='color:gray;font-size:13px'>{r['description']}</span><br>"
                                    f"<span style='color:gray;font-size:12px'>Policy: {r['policy_reference']}</span>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                        st.divider()

                        dim_map = [
                            ("aml_screening",         "AML Screening",         25),
                            ("identity_verification", "Identity Verification", 20),
                            ("account_activity",      "Account Activity",      15),
                            ("proof_of_address",      "Proof of Address",      15),
                            ("beneficial_ownership",  "Beneficial Ownership",  15),
                            ("data_quality",          "Data Quality",          10),
                        ]

                        passing, minor_gaps, failing = [], [], []
                        for dk, label, weight in dim_map:
                            s = result.get(f"{dk}_score", 0)
                            finding = result.get(f"{dk}_details", {}).get("finding", "N/A")
                            entry = {"label": label, "score": s, "weight": weight, "finding": finding}
                            if s >= 70:
                                passing.append(entry)
                            elif s >= 50:
                                minor_gaps.append(entry)
                            else:
                                failing.append(entry)

                        problem_dims = failing + minor_gaps
                        if problem_dims:
                            st.markdown("**Dimension Issues:**")
                            for e in problem_dims:
                                color = COLORS["non_compliant"] if e["score"] < 50 else COLORS["minor"]
                                st.markdown(
                                    f"<div style='border-left:4px solid {color};"
                                    f"padding:8px 12px;margin:6px 0;"
                                    f"background:rgba(255,255,255,0.03);border-radius:4px'>"
                                    f"<strong>{e['label']}</strong> ({e['weight']}% weight) — "
                                    f"Score: <strong>{e['score']}/100</strong><br>"
                                    f"<span style='color:gray;font-size:13px'>{e['finding']}</span>"
                                    f"</div>",
                                    unsafe_allow_html=True
                                )

                        if passing:
                            with st.expander(f"Passing dimensions ({len(passing)})"):
                                for e in passing:
                                    st.markdown(f"**{e['label']}** — {e['score']}/100 — {e['finding']}")

                        all_dims = {e["label"]: e["score"] for e in
                                    sorted(passing + minor_gaps + failing, key=lambda x: x["score"])}
                        fig = go.Figure(go.Bar(
                            x=list(all_dims.values()), y=list(all_dims.keys()), orientation="h",
                            marker_color=[COLORS["compliant"] if s >= 70 else
                                          COLORS["minor"] if s >= 50 else
                                          COLORS["non_compliant"] for s in all_dims.values()],
                            text=list(all_dims.values()), textposition="outside"
                        ))
                        fig.update_layout(xaxis=dict(range=[0, 115], title="Score"),
                                          height=300, margin=dict(l=10, r=10, t=20, b=10),
                                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig, use_container_width=True)

                        with st.expander("Field Provenance & Change History", expanded=False):
                            touch()
                            prov_rows = _get_provenance_table(cid)
                            if prov_rows:
                                st_dataframe_safe(pd.DataFrame(prov_rows), use_container_width=True, hide_index=True)
                            else:
                                st.info("No provenance data for this customer yet.")

                            discrepancies = _get_provenance_store().detect_discrepancies(cid)
                            if discrepancies:
                                st.warning("Discrepancies detected across data sources:")
                                for d in discrepancies:
                                    field = d.get("field_name", "")
                                    vals = d.get("values_by_source", {})
                                    user_val = vals.get("User-Provided", {}).get("value")
                                    ocr_val = vals.get("OCR-Extracted", {}).get("value")
                                    ocr_file = vals.get("OCR-Extracted", {}).get("source_file", "")
                                    ocr_conf = _format_conf_pct(vals.get("OCR-Extracted", {}).get("confidence"))
                                    st.markdown(
                                        f"- **{field}**: User-Provided='{user_val}' vs OCR-Extracted='{ocr_val}' "
                                        f"(from {ocr_file or 'N/A'}, {ocr_conf or 'N/A'} confidence)"
                                    )

                        # Remediation (for Review or Reject)
                        if disposition in ("REJECT", "REVIEW") and role in ("Analyst", "Manager", "Admin"):
                            st.divider()
                            st.markdown("**Remediation Actions**")
                            rc1, rc2 = st.columns(2)
                            with rc1:
                                reason = st.selectbox("Reason Code",
                                                      ["— Select —"] + FALSE_POSITIVE_CODES,
                                                      key=f"r_{cid}")
                            with rc2:
                                note_text = st.text_input("Note (required)", key=f"n_{cid}")
                            ec1, ec2 = st.columns(2)
                            with ec1:
                                if st.button("Escalate", key=f"esc_{cid}"):
                                    if not note_text.strip():
                                        st.error("Note required to escalate.")
                                    else:
                                        touch()
                                        log("CUSTOMER_ESCALATED", customer_id=cid,
                                            details={"note": note_text, "score": score,
                                                     "disposition": disposition})
                                        st.success(f"{cid} escalated. Logged.")
                            with ec2:
                                if st.button("Propose Clear", key=f"clr_{cid}"):
                                    if reason == "— Select —" or not note_text.strip():
                                        st.error("Reason code and note required.")
                                    else:
                                        touch()
                                        log("CLEAR_PROPOSED", customer_id=cid,
                                            details={"reason_code": reason, "note": note_text,
                                                     "disposition": disposition,
                                                     "requires_manager_approval": True})
                                        st.success("Clear proposed. Awaiting manager approval.")

                        history = st.session_state.customer_history.get(cid, [])
                        if len(history) > 1:
                            st.divider()
                            st.markdown("#### Evaluation History — This Session")
                            st_dataframe_safe(pd.DataFrame(history), use_container_width=True, hide_index=True)
                            scores = [h["overall_score"] for h in history]
                            timestamps = [h["timestamp"] for h in history]
                            fig2 = go.Figure(go.Scatter(
                                x=timestamps, y=scores, mode="lines+markers",
                                marker=dict(size=8, color=COLORS["blue"]),
                                line=dict(color=COLORS["blue"]),
                            ))
                            fig2.update_layout(title=f"Score Trend — {cid}",
                                               yaxis=dict(range=[0, 110]),
                                               height=220,
                                               margin=dict(l=10, r=10, t=40, b=10),
                                               plot_bgcolor="rgba(0,0,0,0)",
                                               paper_bgcolor="rgba(0,0,0,0)")
                            st.plotly_chart(fig2, use_container_width=True)

                    except Exception as e:
                        st.error(f"Evaluation error: {e}")

    # ════════════════════════════════════════════════════════
    # TAB 2: BATCH RESULTS
    # ════════════════════════════════════════════════════════
    with tab2:
        touch()
        if not st.session_state.engines_initialized:
            st.warning("No data loaded yet. Upload your files in the Data Management tab to get started.")
        else:
            st.markdown("### Batch Compliance Evaluation")

            n = len(st.session_state.customers_df)
            st.success(f"**{n:,} customers ready to evaluate.** Click the button below to run the full batch.")

            if st.session_state.batch_results is not None:
                st.info(
                    f"Last run: batch **{st.session_state.batch_id}** "
                    f"completed at {st.session_state.batch_run_at}. "
                    "Results are shown below — click the button again to re-run."
                )

            if st.button("Run Full Batch Evaluation", type="primary"):
                touch()
                customer_ids = st.session_state.customers_df["customer_id"].tolist()
                batch_id = str(uuid.uuid4())[:8].upper()
                log("BATCH_RUN_START", batch_id=batch_id,
                    details={"total": len(customer_ids), "initiated_by": user["username"]})

                results, errors = [], []
                bar = st.progress(0)
                txt = st.empty()

                for i, cid in enumerate(customer_ids):
                    try:
                        r = st.session_state.kyc_engine.evaluate_customer(str(cid))
                        results.append(r)
                    except Exception as e:
                        errors.append({"id": cid, "error": str(e)})
                    if i % 50 == 0:
                        bar.progress((i + 1) / len(customer_ids))
                        txt.text(f"{i+1}/{len(customer_ids)}")

                bar.empty()
                txt.empty()

                cols = ["customer_id", "overall_score", "disposition",
                        "aml_screening_score", "identity_verification_score",
                        "account_activity_score", "proof_of_address_score",
                        "beneficial_ownership_score", "data_quality_score",
                        "rationale", "ruleset_version"]

                rdf = pd.DataFrame(results) if results else pd.DataFrame(columns=cols)

                # ── Normalise synthetic portfolio columns if engine couldn't score them ──
                # Map expected_final_decision → disposition (synthetic manifest column)
                if "disposition" not in rdf.columns:
                    if "expected_final_decision" in rdf.columns:
                        rdf = rdf.rename(columns={"expected_final_decision": "disposition"})
                    else:
                        rdf["disposition"] = "REVIEW"

                # Ensure all required columns exist with safe defaults
                if "overall_score" not in rdf.columns:
                    rdf["overall_score"] = 0
                if "rationale" not in rdf.columns:
                    rdf["rationale"] = "Awaiting engine scoring"
                if "ruleset_version" not in rdf.columns:
                    rdf["ruleset_version"] = RULESET_VERSION

                rdf = rdf[[c for c in cols if c in rdf.columns]]
                num_cols = [c for c in rdf.columns if c.endswith("_score")]
                rdf[num_cols] = rdf[num_cols].fillna(0)
                rdf["disposition"] = rdf["disposition"].fillna("REVIEW")

                order = {"REJECT": 0, "REVIEW": 1, "PASS_WITH_NOTES": 2, "PASS": 3}
                rdf["_s"] = rdf["disposition"].map(order).fillna(4)
                rdf = rdf.sort_values(["_s", "overall_score"]).drop(columns=["_s"])

                st.session_state.batch_results = rdf
                st.session_state.batch_id = batch_id
                st.session_state.batch_run_at = datetime.now().strftime("%Y-%m-%d %H:%M")

                n_reject  = len(rdf[rdf["disposition"] == "REJECT"])
                n_review  = len(rdf[rdf["disposition"] == "REVIEW"])
                flagged_ids = rdf[rdf["disposition"].isin(["REJECT", "REVIEW"])]["customer_id"].tolist()

                log("BATCH_RUN_COMPLETE", batch_id=batch_id,
                    details={
                        "evaluated": len(results),
                        "errors": len(errors),
                        "reject": n_reject,
                        "review": n_review,
                        "pass_with_notes": len(rdf[rdf["disposition"] == "PASS_WITH_NOTES"]),
                        "pass": len(rdf[rdf["disposition"] == "PASS"]),
                        "avg_score": float(rdf["overall_score"].mean()),
                        "flagged_customer_ids": flagged_ids,
                        "error_customer_ids": [e["id"] for e in errors],
                        "ruleset_version": rdf["ruleset_version"].iloc[0] if "ruleset_version" in rdf.columns and len(rdf) > 0 else "unknown",
                    })
                st.rerun()

            rdf = st.session_state.batch_results
            if rdf is not None:
                total = len(rdf)
                n_reject = len(rdf[rdf["disposition"] == "REJECT"]) if "disposition" in rdf.columns else 0
                n_review = len(rdf[rdf["disposition"] == "REVIEW"]) if "disposition" in rdf.columns else 0
                n_notes  = len(rdf[rdf["disposition"] == "PASS_WITH_NOTES"]) if "disposition" in rdf.columns else 0
                n_pass   = len(rdf[rdf["disposition"] == "PASS"]) if "disposition" in rdf.columns else 0

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Total", total)
                m2.metric("🚫 Reject", n_reject)
                m3.metric("⚠️ Review", n_review)
                m4.metric("📋 Pass w/ Notes", n_notes)
                m5.metric("✅ Pass", n_pass)

                if "overall_score" in rdf.columns:
                    st.caption(f"Average score: {rdf['overall_score'].mean():.1f}/100")

                ch1, ch2 = st.columns(2)
                with ch1:
                    labels = ["Reject", "Review", "Pass w/ Notes", "Pass"]
                    values = [n_reject, n_review, n_notes, n_pass]
                    colors = [DISPOSITION_CONFIG[d]["color"] for d in
                              ["REJECT", "REVIEW", "PASS_WITH_NOTES", "PASS"]]
                    fig = go.Figure(go.Bar(
                        x=labels, y=values,
                        marker_color=colors,
                        text=values, textposition="outside"
                    ))
                    fig.update_layout(title="Disposition Distribution", height=300,
                                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                with ch2:
                    score_cols = ["aml_screening_score", "identity_verification_score",
                                  "account_activity_score", "proof_of_address_score",
                                  "beneficial_ownership_score", "data_quality_score"]
                    avgs = {col.replace("_score", "").replace("_", " ").title(): rdf[col].mean()
                            for col in score_cols if col in rdf.columns}
                    fig = go.Figure(go.Bar(
                        x=list(avgs.keys()), y=list(avgs.values()),
                        marker_color=COLORS["blue"],
                        text=[f"{v:.1f}" for v in avgs.values()], textposition="outside"
                    ))
                    fig.update_layout(title="Avg Dimension Scores", yaxis=dict(range=[0, 115]),
                                      height=300, plot_bgcolor="rgba(0,0,0,0)",
                                      paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                st.markdown("#### All Results — Reject → Review → Pass with Notes → Pass")
                st_dataframe_safe(rdf, use_container_width=True, hide_index=True)

                buf = io.StringIO()
                rdf.to_csv(buf, index=False)
                st.download_button("Download CSV", buf.getvalue(),
                                   file_name=f"batch_{st.session_state.batch_id}.csv",
                                   mime="text/csv")

    # ════════════════════════════════════════════════════════
    # TAB 3: DATA MANAGEMENT
    # ════════════════════════════════════════════════════════
    with tab3:
        touch()
        st.markdown("### Data Management — Universal Ingestion")
        st.info("CSV, Excel, JSON load directly. Images and PDFs go through OCR then Claude AI. "
                "Set dataset type per file or use Auto-detect.")

        batch_files = st.file_uploader(
            "Drop all files here",
            type=ACCEPTED_TYPES, accept_multiple_files=True, key="batch_uploader"
        )

        file_type_map = {}
        if batch_files:
            type_options = [AUTO_DETECT] + DATASET_OPTIONS
            st.markdown(f"**{len(batch_files)} file(s) selected.**")
            for i in range(0, len(batch_files), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx >= len(batch_files):
                        break
                    f = batch_files[idx]
                    is_unstr = Path(f.name).suffix.lower() not in {".csv", ".xlsx", ".xls", ".json"}
                    with col:
                        dtype = st.selectbox(
                            f"{'OCR' if is_unstr else 'Direct'}: {f.name}",
                            type_options, key=f"bt_{idx}"
                        )
                        if dtype != AUTO_DETECT:
                            st.caption(f"`{KYC_SCHEMAS_HINT.get(dtype, '')}`")
                        file_type_map[idx] = (f, dtype)

        st.divider()
        if st.button("Process & Load All Files", type="primary", use_container_width=True):
            touch()
            if not batch_files:
                st.error("Upload at least one file.")
            else:
                cleaned = {}
                proc_log = []
                bar = st.progress(0)
                txt = st.empty()
                total = len(batch_files)
                st.markdown("#### Step 1: Reading and normalising your data")
                with st.spinner("Running data cleaning pipeline..."):
                    for i, (idx, (fo, dtype)) in enumerate(file_type_map.items()):
                        fn = fo.name
                        txt.text(f"Processing {fn} ({i+1}/{total})")
                        log("FILE_UPLOAD", details={"filename": fn, "size": fo.size,
                                                    "type_selected": dtype})
                        try:
                            df, method, det_type, msg = process_file(fo, fn, dtype)
                            if det_type in cleaned:
                                cleaned[det_type] = pd.concat(
                                    [cleaned[det_type], df], ignore_index=True
                                ).drop_duplicates()
                            else:
                                cleaned[det_type] = df
                            log("DATA_CLEAN", details={"filename": fn, "method": method,
                                                        "detected_type": det_type, "rows": len(df)})
                            proc_log.append({
                                "File": fn,
                                "Dataset type detected": det_type,
                                "Rows loaded": len(df),
                                "Method": "claude_structured" if method == "ocr+llm" else "fallback_pandas",
                                "Status": "OK",
                            })
                        except Exception as e:
                            # Import here to avoid circular import at module top
                            from src.schema_harmonizer import HarmonizationRejected
                            if isinstance(e, HarmonizationRejected):
                                proc_log.append({
                                    "File": fn,
                                    "Dataset type detected": dtype if dtype != AUTO_DETECT else "auto_detect",
                                    "Rows loaded": 0,
                                    "Method": "harmonization_rejected",
                                    "Status": "REJECTED: critical fields below coverage threshold",
                                })
                                # Stash the report for detailed rendering after the loop
                                rejection_reports = st.session_state.get("_rejection_reports", [])
                                rejection_reports.append({
                                    "filename": fn,
                                    "report": e.report,
                                })
                                st.session_state._rejection_reports = rejection_reports
                            else:
                                proc_log.append({
                                    "File": fn,
                                    "Dataset type detected": dtype if dtype != AUTO_DETECT else "auto_detect",
                                    "Rows loaded": 0,
                                    "Method": "error",
                                    "Status": f"FAILED: {str(e)[:120]}",
                                })
                        bar.progress((i + 1) / total)

                bar.empty()
                txt.empty()

                if proc_log:
                    proc_df = pd.DataFrame(proc_log)
                    st_dataframe_safe(proc_df, use_container_width=True, hide_index=True)
                    failed_rows = proc_df[proc_df["Status"].str.startswith("FAILED", na=False)]
                    rejected_rows = proc_df[proc_df["Status"].str.startswith("REJECTED", na=False)]
                    if not failed_rows.empty:
                        for _, row in failed_rows.iterrows():
                            st.error(f"{row['File']}: {row['Status']}")
                    if not rejected_rows.empty:
                        reports = st.session_state.get("_rejection_reports", [])
                        for rep in reports:
                            report = rep["report"]
                            st.error(f"**{rep['filename']} — harmonization rejected**")
                            with st.container(border=True):
                                st.markdown(f"**Dataset type:** `{report['target_type']}`")
                                st.markdown(f"**Rows analyzed:** {report['row_count']}")
                                st.markdown(
                                    f"**Coverage threshold:** {report['threshold_pct']}% "
                                    f"of rows must have each critical field populated"
                                )
                                st.markdown("")
                                st.markdown("**Critical fields below threshold:**")
                                for fd in report["failing_fields"]:
                                    st.markdown(
                                        f"- `{fd['field']}` — {fd['missing_rows']} of {report['row_count']} "
                                        f"rows ({fd['missing_pct']}%) unmappable "
                                        f"(coverage: {fd['coverage_pct']}%)"
                                    )
                                    if fd["likely_source_keys"]:
                                        st.caption(
                                            f"Looked for: {', '.join(fd['likely_source_keys'])} "
                                            "— present but unmappable"
                                        )
                                    else:
                                        st.caption(
                                            "Source DataFrame had no columns resembling this field"
                                        )
                                st.markdown("")
                                st.markdown("**Root cause:** source system did not export the required data.")
                                st.markdown(
                                    "**Fix:** enrich the upstream export with these fields and re-upload. "
                                    "Do not attempt to work around the missing data — these fields drive "
                                    "compliance evaluation and gaps here produce unreliable results."
                                )
                                with st.expander("Technical detail (for data owner)"):
                                    st.json({
                                        "input_columns_seen": report["input_columns_seen"],
                                        "critical_fields_required": report["critical_fields_required"],
                                        "harmonization_source": report["harmonization_source"],
                                        "script_id": report["script_id"],
                                    })
                        # Clear the cached reports so they don't re-render on next run
                        st.session_state._rejection_reports = []
                    if failed_rows.empty and rejected_rows.empty:
                        st.success("All files were processed cleanly through the cleaning pipeline.")

                any_rejected = not rejected_rows.empty if proc_log else False

                if any_rejected:
                    st.error(
                        "Engine not initialized. One or more files were rejected during "
                        "harmonization. Compliance evaluation requires all datasets to pass "
                        "critical-field coverage. Fix the rejected files above and re-upload "
                        "the full set."
                    )
                elif cleaned:
                    tmp_dir = save_to_temp(cleaned)
                    engine, customers = load_engine(tmp_dir)
                    if engine is not None and customers is not None and len(customers) > 0:
                        st.session_state.kyc_engine = engine
                        st.session_state.customers_df = customers
                        st.session_state.engines_initialized = True
                        st.session_state.data_dir = tmp_dir
                        st.session_state.batch_results = None
                        st.session_state.data_source_label = f"Uploaded & cleaned ({', '.join(cleaned.keys())})"
                        _seed_structured_provenance()
                        discrepancy_rows = _collect_discrepancy_report()
                        st.session_state.latest_discrepancy_report = discrepancy_rows
                        log("ENGINE_RELOAD", details={"customers": len(customers),
                                                       "datasets": list(cleaned.keys())})
                        st.success(f"Engine loaded — {len(customers)} customers ready.")
                        st.rerun()
                    else:
                        st.warning("Engine could not initialize. Ensure customers dataset "
                                   "has a customer_id column.")

        if st.session_state.latest_discrepancy_report is not None:
            touch()
            dr = st.session_state.latest_discrepancy_report
            if dr:
                st.divider()
                st.markdown("#### Data Discrepancy Summary")
                disc_df = pd.DataFrame(dr)
                st.warning(f"{disc_df['customer_id'].nunique()} customer(s) with discrepancies detected.")
                st_dataframe_safe(disc_df, use_container_width=True, hide_index=True)
                buf_disc = io.StringIO()
                disc_df.to_csv(buf_disc, index=False)
                st.download_button(
                    "Download Discrepancy CSV",
                    data=buf_disc.getvalue(),
                    file_name=f"discrepancies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )
            else:
                st.info("No data discrepancies detected in current provenance records.")

        st.divider()
        st.markdown("#### Download Cleaned Files")
        if st.session_state.data_dir:
            csv_files = list(Path(st.session_state.data_dir).glob("*.csv"))
            if csv_files:
                cols = st.columns(min(len(csv_files), 3))
                for i, csv_file in enumerate(csv_files):
                    df = pd.read_csv(csv_file)
                    buf = io.StringIO()
                    df.to_csv(buf, index=False)
                    cols[i % 3].download_button(
                        csv_file.name, buf.getvalue(),
                        file_name=csv_file.name, mime="text/csv",
                        key=f"dl_{csv_file.stem}"
                    )

    # ════════════════════════════════════════════════════════
    # TAB 4: DOCUMENT OCR & AI
    # ════════════════════════════════════════════════════════
    with tab4:
        touch()
        st.markdown("### Document OCR & AI Analysis")
        st.markdown("Upload a compliance document. Fields are extracted with citations. "
                    "Confidence below 60% auto-flags for mandatory human review.")

        oc1, oc2 = st.columns([1, 1])
        with oc1:
            uploaded_img = st.file_uploader("Upload document",
                                             type=["png", "jpg", "jpeg", "tiff", "bmp", "pdf"],
                                             key="ocr_up")
            doc_type = st.selectbox("Document Type", [
                "Identity Document (Passport / ID)",
                "Proof of Address", "Corporate Document",
                "Beneficial Ownership Declaration",
                "AML Screening Result", "Other"
            ])
            cid_ocr = st.text_input("Customer ID (for linking)", placeholder="C00001")
        with oc2:
            if uploaded_img:
                st.image(uploaded_img, use_container_width=True)

        if st.button("Run OCR + AI Analysis", type="primary") and uploaded_img:
            touch()
            log("FILE_UPLOAD", details={"filename": uploaded_img.name, "size": uploaded_img.size,
                                         "doc_type": doc_type,
                                         "linked_customer": cid_ocr or None})
            with st.spinner("Running OCR..."):
                try:
                    fbytes = uploaded_img.read()
                    log("OCR_RUN", customer_id=cid_ocr or None, prompt_id="kyc-analysis-v1.0",
                        details={"filename": uploaded_img.name})
                    extracted = run_ocr(fbytes, uploaded_img.name)
                    if not extracted or len(extracted.strip()) < 10:
                        st.error("No text extracted. Try a clearer image.")
                    else:
                        st.success(f"OCR: {len(extracted)} characters extracted")

                        with st.spinner("Analyzing with Claude AI..."):
                            try:
                                import anthropic as ac
                                cfg = get_prompt("kyc-analysis-v1.0")
                                system = cfg.get("system", "Extract KYC fields with citations.")
                                tmpl = cfg.get("user_template", "{ocr_text}")
                                mcfg = cfg.get("model_settings", {})
                                msg = tmpl.format(doc_type=doc_type,
                                                  customer_id=cid_ocr or "Not provided",
                                                  ocr_text=extracted[:3000])
                                log("LLM_CALL", customer_id=cid_ocr or None,
                                    prompt_id="kyc-analysis-v1.0",
                                    details={"doc_type": doc_type, "filename": uploaded_img.name})
                                client = ac.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                                resp = client.messages.create(
                                    model=mcfg.get("model", "claude-opus-4-20250514"),
                                    max_tokens=mcfg.get("max_tokens", 1500),
                                    system=system,
                                    messages=[{"role": "user", "content": msg}]
                                )
                                raw_response = resp.content[0].text
                                analysis = _extract_json_from_response(raw_response)
                                conf = analysis.get("overall_confidence", 0)

                                am1, am2, am3 = st.columns(3)
                                am1.metric("Document Type", analysis.get("document_type", "Unknown"))
                                am2.metric("Confidence", f"{conf*100:.0f}%",
                                           delta="Requires review" if conf < LOW_CONFIDENCE_THRESHOLD else None,
                                           delta_color="inverse" if conf < LOW_CONFIDENCE_THRESHOLD else "normal")
                                am3.metric("Flags", len(analysis.get("compliance_flags", [])))

                                if conf < LOW_CONFIDENCE_THRESHOLD:
                                    st.warning(f"Confidence {conf*100:.0f}% is below the "
                                               f"{LOW_CONFIDENCE_THRESHOLD*100:.0f}% threshold. "
                                               "Auto-flagged for mandatory human review.")
                                    log("FLAG_RAISED", customer_id=cid_ocr or None,
                                        details={"reason": "confidence_below_threshold",
                                                 "confidence": conf,
                                                 "filename": uploaded_img.name})

                                field_pairs = [
                                    ("customer_name", "Name", "name"),
                                    ("document_number", "Document Number", "default"),
                                    ("date_of_birth", "Date of Birth", "dob"),
                                    ("issue_date", "Issue Date", "default"),
                                    ("expiry_date", "Expiry Date", "default"),
                                    ("address", "Address", "address"),
                                    ("nationality", "Nationality", "default"),
                                    ("issuing_authority", "Issuing Authority", "default"),
                                ]
                                extracted_rows = []
                                for key, label, mask_type in field_pairs:
                                    conf_val = float(analysis.get(f"{key}_confidence", 0) or 0)
                                    val = analysis.get(key)
                                    extracted_rows.append({
                                        "field_key": key,
                                        "mask_type": mask_type,
                                        "Field": label,
                                        "Extracted value": mask(val, mask_type) if val else "Not found",
                                        "Confidence": conf_val,
                                    })
                                st.markdown("#### Extracted Fields")
                                extracted_df = pd.DataFrame(extracted_rows)
                                display_df = extracted_df[["Field", "Extracted value", "Confidence"]].copy()
                                display_df["Confidence"] = display_df["Confidence"].map(lambda x: f"{x*100:.0f}%")
                                low_conf_fields = [r for r in extracted_rows if r["Confidence"] < 0.75]

                                def _highlight_low_confidence(row):
                                    conf_pct = int(str(row["Confidence"]).replace("%", "") or 0)
                                    if conf_pct < 75:
                                        return ["background-color: #FFF3CD"] * len(row)
                                    return [""] * len(row)

                                st.dataframe(
                                    display_df.style.apply(_highlight_low_confidence, axis=1),
                                    use_container_width=True,
                                    hide_index=True,
                                )

                                corrected_values = {}
                                if low_conf_fields:
                                    st.warning("Low-confidence fields detected (<75%). Review and correct before rescoring.")
                                    for low in low_conf_fields:
                                        field_key = low["field_key"]
                                        corrected_values[field_key] = st.text_input(
                                            f"{low['Field']} (correction)",
                                            value=str(analysis.get(field_key) or ""),
                                            key=f"ocr_correction_{cid_ocr}_{field_key}",
                                        )

                                for section, label, fn in [
                                    ("compliance_flags", "Compliance Flags", st.warning),
                                    ("risk_indicators", "Risk Indicators", st.error),
                                    ("discrepancies", "Discrepancies", st.error),
                                ]:
                                    items = analysis.get(section, [])
                                    if items:
                                        fn(f"{label}:")
                                        for item in items:
                                            st.markdown(f"- {item}")

                                st.info(analysis.get("extraction_summary", ""))

                                analysis["meta"] = {
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "prompt_version": "kyc-analysis-v1.0",
                                    "confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
                                    "auto_flagged": conf < LOW_CONFIDENCE_THRESHOLD,
                                    "analyzed_by": user["username"],
                                    "note": "All LLM outputs are recommendations. "
                                            "Human decision is authoritative record."
                                }
                                st.download_button(
                                    "Download Analysis JSON",
                                    json.dumps(analysis, indent=2),
                                    file_name=f"ocr_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                                    mime="application/json"
                                )

                                linked_cid = (cid_ocr or "").strip().upper()
                                if linked_cid:
                                    if st.button("Confirm and rescore", type="secondary"):
                                        touch()
                                        confirmed_analysis = dict(analysis)
                                        for field_key, edited in corrected_values.items():
                                            confirmed_analysis[field_key] = edited

                                        written_fields = _record_ocr_analysis_provenance(
                                            linked_cid, confirmed_analysis, uploaded_img.name
                                        )
                                        if _customer_in_engine(linked_cid):
                                            st.session_state.dirty_customers.add(linked_cid)
                                        st.session_state.ocr_analysis_cache[linked_cid] = {
                                            "analysis": confirmed_analysis,
                                            "filename": uploaded_img.name,
                                            "doc_type": doc_type,
                                            "written_fields": [w["field"] for w in written_fields],
                                            "captured_at": datetime.now(timezone.utc).isoformat(),
                                            "confirmed_fields": corrected_values,
                                        }

                                        before_score = None
                                        before_disp = None
                                        hist = st.session_state.customer_history.get(linked_cid, [])
                                        if hist:
                                            before_score = hist[-1].get("overall_score")
                                            before_disp = hist[-1].get("disposition")

                                        updated_fields = _update_single_customer_records(linked_cid, doc_type, confirmed_analysis)
                                        rescored = st.session_state.kyc_engine.evaluate_customer(linked_cid)
                                        after_score = rescored.get("overall_score")
                                        after_disp = rescored.get("disposition")
                                        st.session_state.dirty_customers.discard(linked_cid)

                                        h_entry = {
                                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            "evaluated_by": user["username"],
                                            "overall_score": after_score,
                                            "disposition": after_disp,
                                            "aml_screening_score": rescored.get("aml_screening_score", 0),
                                            "identity_verification_score": rescored.get("identity_verification_score", 0),
                                            "account_activity_score": rescored.get("account_activity_score", 0),
                                            "proof_of_address_score": rescored.get("proof_of_address_score", 0),
                                            "beneficial_ownership_score": rescored.get("beneficial_ownership_score", 0),
                                            "data_quality_score": rescored.get("data_quality_score", 0),
                                        }
                                        st.session_state.customer_history.setdefault(linked_cid, []).append(h_entry)

                                        b1, b2 = st.columns(2)
                                        b1.metric("Before Score / Disposition",
                                                  f"{before_score if before_score is not None else 'N/A'} / {before_disp or 'N/A'}")
                                        b2.metric("After Score / Disposition", f"{after_score} / {after_disp}")

                                        log("ENGINE_RELOAD", customer_id=linked_cid, details={
                                            "scope": "single_customer_rescore",
                                            "doc_type": doc_type,
                                            "source_file": uploaded_img.name,
                                            "updated_fields": updated_fields,
                                            "before_score": before_score,
                                            "before_disposition": before_disp,
                                            "after_score": after_score,
                                            "after_disposition": after_disp,
                                        })
                                        if before_score is None:
                                            st.success("Dataset updated and customer re-scored.")
                                        elif after_score > before_score:
                                            st.success("Case improved after OCR remediation and re-score.")
                                        else:
                                            st.warning("Case did not improve after OCR remediation; follow-up review is required.")
                            except Exception as e:
                                st.error(f"AI analysis failed: {e}")
                except Exception as e:
                    st.error(f"OCR failed: {e}")

    # ════════════════════════════════════════════════════════
    # TAB 5: SYSTEM INFO
    # ════════════════════════════════════════════════════════
    with tab5:
        touch()
        st.markdown("### System Information")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Datasets**")
            if st.session_state.engines_initialized:
                eng = st.session_state.kyc_engine
                st.metric("Customers", len(st.session_state.customers_df))
                st.metric("Screenings",
                          len(eng.screenings) if eng.screenings is not None else 0)
                st.metric("ID Verifications",
                          len(eng.id_verifications) if eng.id_verifications is not None else 0)
                st.metric("Transactions",
                          len(eng.transactions) if eng.transactions is not None else 0)
            else:
                st.info("No datasets loaded.")
        with c2:
            st.markdown("**Active Prompts**")
            if PROMPTS:
                for pid, p in PROMPTS.items():
                    st.markdown(f"- `{pid}` v{p.get('version', '?')} "
                                f"({p.get('created_at', '')[:10]})")
            else:
                st.warning("No prompts loaded. Commit the prompts/ folder to GitHub.")
        st.divider()
        st.markdown(f"""
        **Hosting:** Railway | **Framework:** Streamlit | **Ruleset:** `{RULESET_VERSION}`  
        **Timeout:** {INACTIVITY_TIMEOUT_SEC // 60} min (FFIEC / PSD2) | **Warning at:** {INACTIVITY_WARNING_SEC // 60} min  
        PII clears from memory on session end. Audit trail stores metadata only.
        """)

    # ════════════════════════════════════════════════════════
    # TAB 6: APPROVAL QUEUE
    # ════════════════════════════════════════════════════════
    with tab6:
        touch()
        st.markdown("### Approval Queue")
        if role not in ("Manager", "Admin"):
            st.info("Approvals are handled by a Manager or Admin.")
        else:
            pending = _get_pending_clear_approvals(logger)
            if not pending:
                st.success("No pending clear approvals.")
            else:
                st.caption(f"{len(pending)} pending item(s) awaiting maker-checker approval.")
                for idx, item in enumerate(pending):
                    with st.container(border=True):
                        st.markdown(
                            f"**Customer:** `{item['customer_id']}`  \n"
                            f"**Proposed by:** `{item['proposed_by']}`  \n"
                            f"**Reason code:** {item['reason_code']}  \n"
                            f"**Analyst note:** {item['note']}  \n"
                            f"**Current disposition/score:** {item['disposition']} / {item['score']}  \n"
                            f"**Proposed:** {item['proposed_at_ago']}"
                        )
                        manager_note = st.text_input(
                            "Manager note (required)",
                            key=f"approval_note_{idx}_{item['event_id']}",
                        )
                        c1, c2 = st.columns(2)
                        with c1:
                            approve_disabled = user["username"] == item["proposed_by"]
                            if st.button("Approve Clear", key=f"approve_{idx}_{item['event_id']}", disabled=approve_disabled):
                                if approve_disabled:
                                    st.error("Maker-checker: proposer cannot approve their own clear.")
                                elif not manager_note.strip():
                                    st.error("Manager note is required.")
                                else:
                                    touch()
                                    log(
                                        "CLEAR_APPROVED",
                                        customer_id=item["customer_id"],
                                        details={
                                            "proposed_by": item["proposed_by"],
                                            "reason_code": item["reason_code"],
                                            "manager_note": manager_note,
                                            "approved_by": user["username"],
                                            "approved_at": datetime.now(timezone.utc).isoformat(),
                                        },
                                    )
                                    st.success("Clear approved.")
                                    st.rerun()
                        with c2:
                            if st.button("Reject Clear", key=f"reject_{idx}_{item['event_id']}"):
                                if not manager_note.strip():
                                    st.error("Manager note is required.")
                                else:
                                    touch()
                                    log(
                                        "CLEAR_REJECTED",
                                        customer_id=item["customer_id"],
                                        details={
                                            "proposed_by": item["proposed_by"],
                                            "reason_code": item["reason_code"],
                                            "manager_note": manager_note,
                                            "rejected_by": user["username"],
                                            "rejected_at": datetime.now(timezone.utc).isoformat(),
                                        },
                                    )
                                    st.success("Clear rejected.")
                                    st.rerun()

    # ════════════════════════════════════════════════════════
    # TAB 7: CASES
    # ════════════════════════════════════════════════════════
    with tab7:
        touch()
        st.markdown("### Cases")
        cfg1, cfg2 = st.columns(2)
        with cfg1:
            st.session_state.case_sla_amber_days = st.number_input(
                "SLA amber threshold (days)",
                min_value=1,
                max_value=30,
                value=int(st.session_state.case_sla_amber_days),
                step=1,
                key="sla_amber_input",
            )
        with cfg2:
            st.session_state.case_sla_red_days = st.number_input(
                "SLA red threshold (days)",
                min_value=1,
                max_value=60,
                value=int(st.session_state.case_sla_red_days),
                step=1,
                key="sla_red_input",
            )
        cases = _build_cases(logger)
        if not cases:
            st.info("No cases generated yet in this session.")
        else:
            st.caption(f"{len(cases)} case(s) derived from session audit events.")
            for c in cases:
                with st.expander(f"{c['case_id']} · {c['customer_id']} · {c['case_status']} · {c['sla_badge']}", expanded=False):
                    st.markdown(
                        f"**Case ID:** `{c['case_id']}`  \n"
                        f"**Customer ID:** `{c['customer_id']}`  \n"
                        f"**Current disposition:** {c['current_disposition']}  \n"
                        f"**Current score:** {c['current_score']}  \n"
                        f"**Status:** {c['case_status']}  \n"
                        f"**Opened by:** {c['opened_by']}  \n"
                        f"**Opened at:** {c['opened_at']}  \n"
                        f"**SLA aging:** {c['sla_badge']}"
                    )
                    st.markdown("**Case history (chronological):**")
                    st_dataframe_safe(pd.DataFrame(c["case_history"]), use_container_width=True, hide_index=True)

                    note_key = f"case_note_{c['case_id']}"
                    note_text = st.text_area("Add case note", key=note_key, placeholder="Write note and click Add Note.")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if role in ("Analyst", "Manager", "Admin"):
                            if st.button("Add Note", key=f"add_note_{c['case_id']}"):
                                if not note_text.strip():
                                    st.error("Note is required.")
                                else:
                                    touch()
                                    log("NOTE_ADDED", customer_id=c["customer_id"],
                                        details={"case_id": c["case_id"], "note": note_text.strip()})
                                    st.success("Case note added.")
                                    st.rerun()
                    with col_b:
                        if role in ("Manager", "Admin") and c["case_status"] != "Closed":
                            close_note = st.text_input(
                                "Closure note (required)",
                                key=f"close_note_{c['case_id']}",
                                placeholder="Reason for closure",
                            )
                            if st.button("Close Case", key=f"close_case_{c['case_id']}"):
                                if not close_note.strip():
                                    st.error("Closure note is required.")
                                else:
                                    touch()
                                    log("CASE_CLOSED", customer_id=c["customer_id"],
                                        details={"case_id": c["case_id"], "note": close_note.strip()})
                                    st.success("Case closed.")
                                    st.rerun()

    # ════════════════════════════════════════════════════════
    # TAB 8: AUDIT TRAIL
    # ════════════════════════════════════════════════════════
    with tab8:
        touch()
        log("AUDIT_VIEWER_OPENED", details={"opened_by": user["username"]})
        st.markdown("### Audit Trail")
        st.markdown("Every event is SHA-256 hash-chained within the session and across sessions. "
                    "Use Verify to confirm log integrity.")

        if logger is None or logger.event_count() == 0:
            st.info("No audit events recorded yet in this session.")
        else:
            edf = logger.get_events_df()

            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                fa = st.selectbox("Filter by Action",
                                  ["All"] + sorted(edf["Action"].unique().tolist()))
            with fc2:
                fc = st.text_input("Filter by Customer ID")
            with fc3:
                fu = st.selectbox("Filter by User",
                                  ["All"] + sorted(edf["User"].unique().tolist()))

            filtered = edf.copy()
            if fa != "All":
                filtered = filtered[filtered["Action"] == fa]
            if fc.strip():
                filtered = filtered[
                    filtered["Customer ID"].str.contains(fc.strip().upper(), na=False)]
            if fu != "All":
                filtered = filtered[filtered["User"] == fu]

            st.markdown(f"**{len(filtered)} of {logger.event_count()} events**")
            st_dataframe_safe(filtered, use_container_width=True, hide_index=True)

            touch()
            st.divider()
            st.markdown("#### Data Provenance Summary")
            prov = _get_provenance_store()
            p_customers = prov.get_customer_ids()
            if not p_customers:
                st.info("No provenance data captured yet.")
            else:
                total_fields = 0
                total_discrepancies = 0
                for pcid in p_customers:
                    total_fields += len(prov.get_all_fields(pcid))
                    total_discrepancies += len(prov.detect_discrepancies(pcid))
                ps1, ps2, ps3 = st.columns(3)
                ps1.metric("Total Fields Tracked", total_fields)
                ps2.metric("Customers with Provenance", len(p_customers))
                ps3.metric("Total Discrepancies", total_discrepancies)

                chosen = st.selectbox("View customer provenance history", p_customers, key="prov_customer_pick")
                hist_rows = prov.get_customer_history_rows(chosen)
                if hist_rows:
                    show_df = pd.DataFrame(hist_rows)
                    show_df["Confidence"] = show_df["Confidence"].apply(_format_conf_pct)
                    st_dataframe_safe(show_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No provenance history rows for selected customer.")

            st.divider()
            v1, v2 = st.columns(2)
            with v1:
                if st.button("Verify Log Integrity"):
                    touch()
                    sys.path.insert(0, str(Path.cwd() / "src"))
                    from audit_logger import verify_session_log
                    result = verify_session_log(logger.finalize())
                    if result["valid"]:
                        st.success(result["details"])
                    else:
                        st.error(result["details"])
            with v2:
                log_json = logger.export_json()
                log("AUDIT_EXPORTED", details={"events": logger.event_count(),
                                                "by": user["username"]})
                st.download_button(
                    "Download Session Audit Log",
                    log_json,
                    file_name=f"audit_{user['user_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

            if role in ("Manager", "Admin"):
                st.divider()
                st.markdown("#### Export Package")
                if st.button("Generate Export Package", type="primary"):
                    touch()
                    _, _, manifest = _build_export_package(logger, user)
                    log("EXPORT_PACKAGE_CREATED", details={
                        "created_by": user["username"],
                        "files_included": manifest,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    })
                    export_bytes, export_name, manifest = _build_export_package(logger, user)
                    st.session_state.latest_export_package = {
                        "bytes": export_bytes,
                        "name": export_name,
                        "manifest": manifest,
                    }
                    st.success("Export package generated.")

                pkg = st.session_state.latest_export_package
                if pkg:
                    st.caption("Included files:")
                    st_dataframe_safe(pd.DataFrame(pkg["manifest"]), use_container_width=True, hide_index=True)
                    st.download_button(
                        "Download Export Package (.zip)",
                        data=pkg["bytes"],
                        file_name=pkg["name"],
                        mime="application/zip",
                    )



# ── Entry point ───────────────────────────────────────────────────────────────

if not st.session_state.authenticated:
    render_login()
else:
    if not check_timeout():
        render_login()
    else:
        render_main()

st.divider()
st.markdown(
    f"<div style='text-align:center;color:gray;font-size:11px'>"
    f"Apexon KYC Compliance Platform | "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
    f"</div>",
    unsafe_allow_html=True
)
