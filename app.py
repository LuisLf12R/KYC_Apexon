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
from src.dataframe_arrow_compat import ensure_arrow_compatible
from kyc_dashboard.components import (
    disposition_badge,
    show_disposition,
    mask,
    _format_conf_pct,
    st_dataframe_safe,
)
from kyc_dashboard.styles import inject_styles
from kyc_dashboard.state import (
    INACTIVITY_WARNING_SEC,
    INACTIVITY_TIMEOUT_SEC,
    RULESET_VERSION,
    ACCEPTED_TYPES,
    DATASET_OPTIONS,
    AUTO_DETECT,
    LOW_CONFIDENCE_THRESHOLD,
    DEFAULT_SLA_AMBER_DAYS,
    DEFAULT_SLA_RED_DAYS,
    KYC_SCHEMAS_HINT,
    FALSE_POSITIVE_CODES,
    COLORS,
    DISPOSITION_CONFIG,
    _DEFAULTS,
    touch,
    get_logger,
    log,
    check_timeout,
    _force_logout,
    can_unmask,
)
from kyc_dashboard.tabs import individual, batch, data_management, document_ocr, system_info, approval_queue, cases, audit_trail

load_dotenv()
st.set_page_config(
    page_title="KYC Compliance Platform",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_styles()

# ── API keys ──────────────────────────────────────────────────────────────────

@st.cache_resource
def init_api_keys():
    try:
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        if not claude_key:
            return False, "ANTHROPIC_API_KEY not configured"
        os.environ["ANTHROPIC_API_KEY"] = claude_key

        # Prefer explicit ADC path if already provided by runtime/deployment.
        google_adc_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if google_adc_path and Path(google_adc_path).exists():
            return True, "OK"

        google_creds = (
            google_adc_path
            or os.getenv("GOOGLE_VISION_JSON_PATH")
            or os.getenv("GOOGLE_VISION_JSON_BASE64")
            or os.getenv("GOOGLE_VISION_JSON")
        )
        if not google_creds:
            return False, "Google Vision API key not configured"

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



# ── Engine loader ─────────────────────────────────────────────────────────────

def load_engine(data_dir):
    try:
        from src.kyc_engine import KYCComplianceEngine
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
    df = ensure_arrow_compatible(df, dataset_type=dataset_type)
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
    return ensure_arrow_compatible(pd.DataFrame(records), dataset_type=dataset_type)

def autodetect(sample, filename):
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
        individual.render(user, role, logger)

    with tab2:
        batch.render(user, role, logger)

    with tab3:
        data_management.render(user, role, logger)

    with tab4:
        document_ocr.render(user, role, logger)

    with tab5:
        system_info.render(user, role, logger)

    with tab6:
        approval_queue.render(user, role, logger)

    with tab7:
        cases.render(user, role, logger)

    with tab8:
        audit_trail.render(user, role, logger)

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
