from datetime import datetime, timezone

import streamlit as st

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


def init_state():
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_logger():
    return st.session_state.get("audit_logger")


def log(action_type, details=None, customer_id=None, batch_id=None, snapshot=None, prompt_id=None):
    lg = get_logger()
    if lg:
        lg.log(action_type, details=details, customer_id=customer_id,
               batch_id=batch_id, snapshot=snapshot, prompt_id=prompt_id)


def touch():
    st.session_state.last_activity = datetime.now(timezone.utc)


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


def can_unmask():
    u = st.session_state.current_user
    return u and u.get("role") in ("Manager", "Admin")
