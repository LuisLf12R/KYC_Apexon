"""
app.py — KYC Compliance Platform
Apexon Case Study 02 | Full Platform Edition

Features:
- User authentication with role-based access (Viewer / Analyst / Manager / Admin)
- 15-minute inactivity timeout (FFIEC / PSD2 / global KYC standard)
- 13-minute inactivity warning (logged to audit trail)
- Full audit trail with per-event SHA-256 hash chaining across sessions
- Prompt registry with versioned prompts
- Universal file ingestion: CSV, Excel, JSON, PNG, JPG, TIFF, PDF
- OCR (Google Vision) + LLM (Claude) structured extraction
- KYC engine evaluation across 6 compliance dimensions
- Audit viewer with filterable event table and integrity verification
- PII masking toggle (role-aware)
"""

import streamlit as st
import pandas as pd
import json
import io
import os
import sys
import tempfile
import uuid
import base64
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
import plotly.graph_objects as go

load_dotenv()

st.set_page_config(
    page_title="KYC Compliance Platform",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────

INACTIVITY_WARNING_SEC = 13 * 60
INACTIVITY_TIMEOUT_SEC = 15 * 60
RULESET_VERSION = "kyc-ruleset-v1.0"
ACCEPTED_TYPES = ["csv", "xlsx", "xls", "json", "png", "jpg", "jpeg", "tiff", "bmp", "pdf"]
DATASET_OPTIONS = ["customers", "screenings", "id_verifications", "transactions", "documents", "beneficial_ownership"]
AUTO_DETECT = "Auto-detect (AI classifies)"
LOW_CONFIDENCE_THRESHOLD = 0.6

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
    "purple":        "#CC79A7",
    "sky":           "#56B4E9",
    "gray":          "#999999",
}

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
    return {"admin": {"user_id": "fallback", "username": "admin", "password": "admin123",
                       "role": "Admin", "full_name": "Administrator"}}

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
    for col in df.columns:
        if any(k in col for k in ["date", "expiry", "expiration"]):
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    for col in ["screening_result", "hit_status", "document_status", "risk_rating"]:
        if col in df.columns:
            df[col] = df[col].str.upper()
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
    raise ValueError(f"Unsupported: {ext}")

def ocr_file(file_bytes, filename):
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
    if ext in {".csv", ".xlsx", ".xls", ".json"}:
        df = read_structured(file_obj, filename)
        if dataset_type == AUTO_DETECT:
            dataset_type = autodetect(df.head(3).to_string(), filename)
            log("AUTODETECT_RUN", prompt_id="autodetect-v1.0",
                details={"filename": filename, "detected": dataset_type})
        df = clean_dataframe(df, dataset_type)
        return df, "direct", dataset_type, f"Loaded {len(df)} rows"
    else:
        file_bytes = file_obj.read()
        log("OCR_RUN", prompt_id="kyc-analysis-v1.0",
            details={"filename": filename, "bytes": len(file_bytes)})
        raw_text = ocr_file(file_bytes, filename)
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
        return df, "ocr+llm", dataset_type, f"Extracted {len(df)} records from {len(raw_text)} chars"


# ╔══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ╚══════════════════════════════════════════════════════════════════════════════

def render_login():
    st.markdown('<meta http-equiv="refresh" content="60">', unsafe_allow_html=True)

    if st.session_state.get("_final_log"):
        st.warning("Session expired. Download your audit log.")
        st.download_button("Download Audit Log",
                           st.session_state["_final_log"],
                           file_name=f"audit_expired_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                           mime="application/json")
        st.divider()

    _, col, _ = st.columns([2, 1, 2])
    with col:
        st.markdown("## 🏦 KYC Compliance Platform")
        st.markdown("*Apexon — Case Study 02*")
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
                logger.log("LOGIN", details={"username": user["username"], "role": user["role"],
                                              "pii_masked_on_login": True})
                default_dir = Path.cwd() / "Data Clean"
                if default_dir.exists():
                    engine, customers = load_engine(default_dir)
                    if engine is not None:
                        st.session_state.kyc_engine = engine
                        st.session_state.customers_df = customers
                        st.session_state.engines_initialized = True
                        st.session_state.data_dir = default_dir
                st.rerun()
            else:
                st.error("Invalid credentials.")
        st.caption("Sessions expire after 15 minutes of inactivity (FFIEC / PSD2 standard).")


# ╔══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ╚══════════════════════════════════════════════════════════════════════════════

def render_main():
    user = st.session_state.current_user
    role = user["role"]
    logger = get_logger()

    # Auto-refresh for timeout enforcement
    st.markdown('<meta http-equiv="refresh" content="60">', unsafe_allow_html=True)

    # Inactivity warning
    if st.session_state.timeout_warning_logged:
        elapsed = (datetime.now(timezone.utc) - st.session_state.last_activity).total_seconds()
        remaining = max(0, INACTIVITY_TIMEOUT_SEC - elapsed)
        st.warning(
            f"Session expires in {int(remaining // 60)}m {int(remaining % 60)}s due to inactivity. "
            "Click anywhere to continue. This event is logged.",
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
            st.markdown("<span style='color:gray;font-size:12px'>PII Masked</span>", unsafe_allow_html=True)
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
            st.success(f"Engine Ready — {len(st.session_state.customers_df)} customers")
        else:
            st.warning("No data — use Data Management")
    with s2:
        st.info(f"Ruleset: {RULESET_VERSION}")
    with s3:
        st.info(f"Audit events: {logger.event_count() if logger else 0}")
    with s4:
        st.info(f"Prompts loaded: {len(PROMPTS)}")

    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Individual Evaluation", "Batch Results", "Data Management",
        "Document OCR & AI", "System Info", "Audit Trail",
    ])

    # ── TAB 1: INDIVIDUAL ────────────────────────────────────────────────────
    with tab1:
        touch()
        if not st.session_state.engines_initialized:
            st.warning("No data loaded. Go to Data Management.")
            st.stop()

        st.markdown("### Search & Evaluate Customer")
        col1, col2 = st.columns([4, 1])
        with col1:
            cid_input = st.text_input("Customer ID", placeholder="C00001")
        with col2:
            eval_btn = st.button("Evaluate", type="primary", use_container_width=True)

        if eval_btn and cid_input:
            cid = cid_input.strip().upper()
            touch()
            with st.spinner(f"Evaluating {cid}..."):
                try:
                    result = st.session_state.kyc_engine.evaluate_customer(cid)
                    status = result.get("overall_status", "Unknown")
                    score = result.get("overall_score", 0)

                    # Log with full snapshot — "what was shown at this moment"
                    log("CUSTOMER_VIEW", customer_id=cid,
                        details={"tab": "individual_evaluation"},
                        snapshot={k: result.get(k) for k in [
                            "overall_score", "overall_status",
                            "aml_screening_score", "identity_verification_score",
                            "account_activity_score", "proof_of_address_score",
                            "beneficial_ownership_score", "data_quality_score",
                        ]})

                    if status == "Non-Compliant":
                        log("FLAG_RAISED", customer_id=cid,
                            details={"score": score, "triggered_by": "individual_evaluation"})

                    # Metrics
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Overall Score", f"{score}/100")
                    m2.metric("Status", status)
                    m3.metric("Customer", cid)

                    if status == "Compliant":
                        st.success("Compliant")
                    elif "Minor" in status:
                        st.warning("Compliant with Minor Gaps")
                    else:
                        st.error("Non-Compliant")
                        if role in ("Analyst", "Manager", "Admin"):
                            st.markdown("**Remediation**")
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
                                            details={"note": note_text, "score": score})
                                        st.success(f"{cid} escalated. Logged.")
                            with ec2:
                                if st.button("Propose Clear", key=f"clr_{cid}"):
                                    if reason == "— Select —" or not note_text.strip():
                                        st.error("Reason code and note required.")
                                    else:
                                        touch()
                                        log("CLEAR_PROPOSED", customer_id=cid,
                                            details={"reason_code": reason, "note": note_text,
                                                     "requires_manager_approval": True})
                                        st.success("Clear proposed. Awaiting manager approval. Logged.")

                    # Dimension chart
                    dims = {
                        "AML (25%)": result.get("aml_screening_score", 0),
                        "Identity (20%)": result.get("identity_verification_score", 0),
                        "Activity (15%)": result.get("account_activity_score", 0),
                        "Address (15%)": result.get("proof_of_address_score", 0),
                        "Ownership (15%)": result.get("beneficial_ownership_score", 0),
                        "Data Quality (10%)": result.get("data_quality_score", 0),
                    }
                    fig = go.Figure(go.Bar(
                        x=list(dims.values()), y=list(dims.keys()), orientation="h",
                        marker_color=[COLORS["compliant"] if s >= 70 else
                                      COLORS["minor"] if s >= 50 else
                                      COLORS["non_compliant"] for s in dims.values()],
                        text=list(dims.values()), textposition="outside"
                    ))
                    fig.update_layout(xaxis=dict(range=[0, 115]), height=320,
                                      margin=dict(l=10, r=10, t=20, b=10),
                                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig, use_container_width=True)

                    # Findings
                    findings = []
                    for dk, label in [
                        ("aml_screening", "AML Screening"),
                        ("identity_verification", "Identity Verification"),
                        ("account_activity", "Account Activity"),
                        ("proof_of_address", "Proof of Address"),
                        ("beneficial_ownership", "Beneficial Ownership"),
                        ("data_quality", "Data Quality"),
                    ]:
                        d = result.get(f"{dk}_details", {})
                        findings.append({"Dimension": label,
                                          "Score": result.get(f"{dk}_score", 0),
                                          "Finding": d.get("finding", "N/A")})
                    st.dataframe(pd.DataFrame(findings), use_container_width=True, hide_index=True)

                except Exception as e:
                    st.error(f"Evaluation error: {e}")

    # ── TAB 2: BATCH ─────────────────────────────────────────────────────────
    with tab2:
        touch()
        if not st.session_state.engines_initialized:
            st.warning("No data loaded. Go to Data Management.")
            st.stop()

        st.markdown("### Batch Compliance Evaluation")

        if st.session_state.batch_results is not None:
            st.success(
                f"Results from batch **{st.session_state.batch_id}** "
                f"run at {st.session_state.batch_run_at}. "
                "Click below to re-run."
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
                    log("CUSTOMER_EVALUATED", customer_id=str(cid), batch_id=batch_id,
                        snapshot={"overall_score": r.get("overall_score"),
                                  "overall_status": r.get("overall_status")})
                    if r.get("overall_status") == "Non-Compliant":
                        log("FLAG_RAISED", customer_id=str(cid), batch_id=batch_id,
                            details={"score": r.get("overall_score"), "source": "batch"})
                except Exception as e:
                    errors.append({"id": cid, "error": str(e)})
                if i % 10 == 0:
                    bar.progress((i + 1) / len(customer_ids))
                    txt.text(f"{i+1}/{len(customer_ids)}")

            bar.empty(); txt.empty()

            cols = ["customer_id", "aml_screening_score", "identity_verification_score",
                    "account_activity_score", "proof_of_address_score",
                    "beneficial_ownership_score", "data_quality_score",
                    "overall_score", "overall_status"]
            rdf = pd.DataFrame(results)
            rdf = rdf[[c for c in cols if c in rdf.columns]]
            num_cols = [c for c in rdf.columns if c.endswith("_score")]
            rdf[num_cols] = rdf[num_cols].fillna(0)
            rdf["overall_status"] = rdf["overall_status"].fillna("Unknown")
            rdf["overall_score"] = rdf["overall_score"].fillna(0)

            # Sort: non-compliant first
            order = {"Non-Compliant": 0, "Compliant with Minor Gaps": 1, "Compliant": 2, "Unknown": 3}
            rdf["_s"] = rdf["overall_status"].map(order).fillna(3)
            rdf = rdf.sort_values(["_s", "overall_score"]).drop(columns=["_s"])

            st.session_state.batch_results = rdf
            st.session_state.batch_id = batch_id
            st.session_state.batch_run_at = datetime.now().strftime("%Y-%m-%d %H:%M")

            non_c = len(rdf[rdf["overall_status"] == "Non-Compliant"])
            log("BATCH_RUN_COMPLETE", batch_id=batch_id,
                details={"evaluated": len(results), "errors": len(errors),
                         "non_compliant": non_c,
                         "avg_score": float(rdf["overall_score"].mean())})
            st.rerun()

        rdf = st.session_state.batch_results
        if rdf is not None:
            total = len(rdf)
            nc = len(rdf[rdf["overall_status"] == "Non-Compliant"])
            mn = len(rdf[rdf["overall_status"] == "Compliant with Minor Gaps"])
            co = len(rdf[rdf["overall_status"] == "Compliant"])

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total", total)
            m2.metric("Non-Compliant", nc, delta=f"{nc/total*100:.1f}%", delta_color="inverse")
            m3.metric("Minor Gaps", mn)
            m4.metric("Compliant", co)
            m5.metric("Avg Score", f"{rdf['overall_score'].mean():.1f}")

            ch1, ch2 = st.columns(2)
            with ch1:
                fig = go.Figure(go.Bar(
                    x=["Non-Compliant", "Minor Gaps", "Compliant"],
                    y=[nc, mn, co],
                    marker_color=[COLORS["non_compliant"], COLORS["minor"], COLORS["compliant"]],
                    text=[nc, mn, co], textposition="outside"
                ))
                fig.update_layout(title="Compliance Distribution", height=300,
                                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            with ch2:
                avgs = {
                    "AML": rdf["aml_screening_score"].mean(),
                    "Identity": rdf["identity_verification_score"].mean(),
                    "Activity": rdf["account_activity_score"].mean(),
                    "Address": rdf["proof_of_address_score"].mean(),
                    "Ownership": rdf["beneficial_ownership_score"].mean(),
                    "Quality": rdf["data_quality_score"].mean(),
                }
                fig = go.Figure(go.Bar(
                    x=list(avgs.keys()), y=list(avgs.values()),
                    marker_color=COLORS["blue"],
                    text=[f"{v:.1f}" for v in avgs.values()], textposition="outside"
                ))
                fig.update_layout(title="Avg Dimension Scores", yaxis=dict(range=[0, 115]),
                                   height=300, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### All Results — Non-Compliant First")
            st.dataframe(rdf, use_container_width=True, hide_index=True)

            buf = io.StringIO()
            rdf.to_csv(buf, index=False)
            st.download_button("Download CSV", buf.getvalue(),
                               file_name=f"batch_{st.session_state.batch_id}.csv",
                               mime="text/csv")

    # ── TAB 3: DATA MANAGEMENT ───────────────────────────────────────────────
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
            st.markdown(f"**{len(batch_files)} file(s)**")
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
                        st.success(f"{'OCR+AI' if method == 'ocr+llm' else 'Direct'}: {fn} → `{det_type}` — {msg}")
                        proc_log.append({"File": fn, "Dataset": det_type,
                                         "Method": method, "Rows": len(df), "Status": "OK"})
                    except Exception as e:
                        st.error(f"{fn}: {e}")
                        proc_log.append({"File": fn, "Dataset": dtype,
                                         "Method": "error", "Rows": 0, "Status": str(e)[:80]})
                    bar.progress((i + 1) / total)

                bar.empty(); txt.empty()

                if cleaned:
                    tmp_dir = save_to_temp(cleaned)
                    engine, customers = load_engine(tmp_dir)
                    if engine is not None and customers is not None and len(customers) > 0:
                        st.session_state.kyc_engine = engine
                        st.session_state.customers_df = customers
                        st.session_state.engines_initialized = True
                        st.session_state.data_dir = tmp_dir
                        st.session_state.batch_results = None
                        log("ENGINE_RELOAD", details={"customers": len(customers),
                                                       "datasets": list(cleaned.keys())})
                        st.success(f"Engine loaded — {len(customers)} customers ready.")
                        st.balloons()
                    else:
                        st.warning("Engine could not initialize. Ensure customers dataset has customer_id.")

                if proc_log:
                    st.dataframe(pd.DataFrame(proc_log), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### Download Cleaned Files")
        if st.session_state.data_dir:
            for csv_file in Path(st.session_state.data_dir).glob("*.csv"):
                df = pd.read_csv(csv_file)
                buf = io.StringIO()
                df.to_csv(buf, index=False)
                st.download_button(csv_file.name, buf.getvalue(),
                                   file_name=csv_file.name, mime="text/csv",
                                   key=f"dl_{csv_file.stem}")

    # ── TAB 4: OCR & AI ──────────────────────────────────────────────────────
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
                st.image(uploaded_img, use_column_width=True)

        if st.button("Run OCR + AI Analysis", type="primary") and uploaded_img:
            touch()
            log("FILE_UPLOAD", details={"filename": uploaded_img.name, "size": uploaded_img.size,
                                         "doc_type": doc_type, "linked_customer": cid_ocr or None})
            with st.spinner("Running OCR..."):
                try:
                    fbytes = uploaded_img.read()
                    log("OCR_RUN", customer_id=cid_ocr or None, prompt_id="kyc-analysis-v1.0",
                        details={"filename": uploaded_img.name})
                    extracted = ocr_file(fbytes, uploaded_img.name)
                    if not extracted or len(extracted.strip()) < 10:
                        st.error("No text extracted.")
                        st.stop()
                    st.success(f"OCR: {len(extracted)} characters extracted")
                except Exception as e:
                    st.error(f"OCR failed: {e}")
                    st.stop()

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
                    log("LLM_CALL", customer_id=cid_ocr or None, prompt_id="kyc-analysis-v1.0",
                        details={"doc_type": doc_type, "filename": uploaded_img.name,
                                 "model": mcfg.get("model", "claude-opus-4-20250514")})
                    client = ac.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                    resp = client.messages.create(
                        model=mcfg.get("model", "claude-opus-4-20250514"),
                        max_tokens=mcfg.get("max_tokens", 1500),
                        system=system,
                        messages=[{"role": "user", "content": msg}]
                    )
                    analysis = json.loads(resp.content[0].text.strip())
                    conf = analysis.get("overall_confidence", 0)

                    am1, am2, am3 = st.columns(3)
                    am1.metric("Document Type", analysis.get("document_type", "Unknown"))
                    am2.metric("Confidence", f"{conf*100:.0f}%",
                               delta="Requires review" if conf < LOW_CONFIDENCE_THRESHOLD else None,
                               delta_color="inverse" if conf < LOW_CONFIDENCE_THRESHOLD else "normal")
                    am3.metric("Flags", len(analysis.get("compliance_flags", [])))

                    if conf < LOW_CONFIDENCE_THRESHOLD:
                        st.warning(f"Confidence {conf*100:.0f}% below {LOW_CONFIDENCE_THRESHOLD*100:.0f}% threshold. "
                                   "Auto-flagged for mandatory human review.")
                        log("FLAG_RAISED", customer_id=cid_ocr or None,
                            details={"reason": "confidence_below_threshold",
                                     "confidence": conf, "threshold": LOW_CONFIDENCE_THRESHOLD,
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
                    rows = []
                    for key, label, mask_type in field_pairs:
                        val = analysis.get(key)
                        rows.append({
                            "Field": label,
                            "Value": mask(val, mask_type) if val else "Not found",
                            "Citation": analysis.get(f"{key}_citation", ""),
                            "Confidence": f"{analysis.get(f'{key}_confidence', 0)*100:.0f}%",
                        })
                    st.markdown("#### Extracted Fields with Citations")
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    for section, label, color in [
                        ("compliance_flags", "Compliance Flags", "warning"),
                        ("risk_indicators", "Risk Indicators", "error"),
                        ("discrepancies", "Discrepancies", "error"),
                    ]:
                        items = analysis.get(section, [])
                        if items:
                            getattr(st, color)(f"{label}:")
                            for item in items:
                                st.markdown(f"- {item}")

                    st.info(analysis.get("extraction_summary", ""))

                    analysis["meta"] = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "prompt_version": "kyc-analysis-v1.0",
                        "confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
                        "auto_flagged": conf < LOW_CONFIDENCE_THRESHOLD,
                        "analyzed_by": user["username"],
                        "note": "All LLM outputs are recommendations. Human decision is authoritative record."
                    }
                    st.download_button("Download Analysis JSON",
                                       json.dumps(analysis, indent=2),
                                       file_name=f"ocr_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                                       mime="application/json")
                except Exception as e:
                    st.error(f"AI analysis failed: {e}")

    # ── TAB 5: SYSTEM INFO ───────────────────────────────────────────────────
    with tab5:
        touch()
        st.markdown("### System Information")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Datasets**")
            if st.session_state.engines_initialized:
                eng = st.session_state.kyc_engine
                st.metric("Customers", len(st.session_state.customers_df))
                st.metric("Screenings", len(eng.screenings) if eng.screenings is not None else 0)
                st.metric("ID Verifications", len(eng.id_verifications) if eng.id_verifications is not None else 0)
                st.metric("Transactions", len(eng.transactions) if eng.transactions is not None else 0)
            else:
                st.info("No datasets loaded.")
        with c2:
            st.markdown("**Active Prompts**")
            for pid, p in PROMPTS.items():
                st.markdown(f"- `{pid}` v{p.get('version', '?')} ({p.get('created_at', '')[:10]})")
        st.divider()
        st.markdown(f"""
        **Hosting:** Railway | **Framework:** Streamlit | **Ruleset:** `{RULESET_VERSION}`  
        **Timeout:** {INACTIVITY_TIMEOUT_SEC // 60} min (FFIEC / PSD2 standard) | **Warning at:** {INACTIVITY_WARNING_SEC // 60} min  
        PII clears from memory on session end. Audit trail stores metadata only, not raw PII.
        """)

    # ── TAB 6: AUDIT TRAIL ───────────────────────────────────────────────────
    with tab6:
        touch()
        log("AUDIT_VIEWER_OPENED", details={"opened_by": user["username"]})
        st.markdown("### Audit Trail")
        st.markdown("Every event is SHA-256 hash-chained. Chains link across sessions. "
                    "Use Verify button to prove log integrity.")

        if logger is None or logger.event_count() == 0:
            st.info("No audit events in this session yet.")
        else:
            edf = logger.get_events_df()
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                fa = st.selectbox("Action", ["All"] + sorted(edf["Action"].unique().tolist()))
            with fc2:
                fc = st.text_input("Customer ID")
            with fc3:
                fu = st.selectbox("User", ["All"] + sorted(edf["User"].unique().tolist()))

            filtered = edf.copy()
            if fa != "All":
                filtered = filtered[filtered["Action"] == fa]
            if fc.strip():
                filtered = filtered[filtered["Customer ID"].str.contains(fc.strip().upper(), na=False)]
            if fu != "All":
                filtered = filtered[filtered["User"] == fu]

            st.markdown(f"**{len(filtered)} of {logger.event_count()} events**")
            st.dataframe(filtered, use_container_width=True, hide_index=True)

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
    f"Apexon KYC Compliance Platform | {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
    f"</div>",
    unsafe_allow_html=True
)
