"""Backend-backed operations dashboard."""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
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
_QUEUE_COLUMNS = [
    "customer_id",
    "customer_name_display",
    "entity_type",
    "confidence_display",
    "decision",
    "flags",
    "last_updated",
]
_SNAPSHOT_FIELDS = [
    "overall_score",
    "disposition",
    "aml_screening_score",
    "identity_verification_score",
    "account_activity_score",
    "proof_of_address_score",
    "beneficial_ownership_score",
    "data_quality_score",
    "source_of_wealth_score",
    "crs_fatca_score",
]


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
                "_sort_key",
                ascending=False,
                na_position="last",
            )
            return rows.iloc[0].drop(labels=["_sort_key"]).to_dict()
        except Exception:
            pass
    return rows.iloc[0].to_dict()


def _confidence_score(result: Dict[str, Any]) -> int:
    return int(round(max(0.0, min(100.0, _as_float(result.get("overall_score"))))))


def _confidence_tier(score: int) -> str:
    if score >= 85:
        return "High"
    if score >= 70:
        return "Medium"
    return "Low"


def _decision_label(disposition: str) -> str:
    if str(disposition or "").upper() in ("PASS", "PASS_WITH_NOTES"):
        return "PASS"
    return "FAIL"


def _entity_label(value: str) -> str:
    cleaned = _safe_str(value).upper()
    if not cleaned:
        return "Unknown"
    if any(token in cleaned for token in ["LEGAL", "CORP", "COMPANY", "ENTITY"]):
        return "Corporate"
    if "INDIVIDUAL" in cleaned:
        return "Individual"
    return cleaned.title()


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


def _weakest_dimension(result: Dict[str, Any]) -> str:
    dims = []
    for field in [
        "aml_screening_score",
        "identity_verification_score",
        "account_activity_score",
        "proof_of_address_score",
        "beneficial_ownership_score",
        "data_quality_score",
        "source_of_wealth_score",
        "crs_fatca_score",
    ]:
        dims.append((field, _as_float(result.get(field))))
    dims = [item for item in dims if item[1] > 0]
    if not dims:
        return ""
    dims.sort(key=lambda item: item[1])
    return dims[0][0].replace("_score", "").replace("_", " ").title()


def _build_notes(result: Dict[str, Any], rule_ids: List[str]) -> str:
    disposition = _safe_str(result.get("disposition")).upper()
    rationale = _safe_str(result.get("rationale"))
    weakest = _weakest_dimension(result)
    if rule_ids and disposition in ("REJECT", "REVIEW"):
        return "Triggered: " + ", ".join(rule_ids[:3])
    if rationale:
        return rationale[:180]
    if weakest:
        return "Weakest dimension: " + weakest
    return "No material flags"


def _build_flags(result: Dict[str, Any], rule_ids: List[str]) -> List[str]:
    flags: List[str] = []
    if _safe_str(result.get("rationale")) or rule_ids:
        flags.append("Note")
    if _as_float(result.get("beneficial_ownership_score")) and _as_float(result.get("beneficial_ownership_score")) < 70:
        flags.append("UBO")
    if any(_as_float(result.get(field)) < 70 for field in ["identity_verification_score", "proof_of_address_score"]):
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


def _format_ago(value: Any) -> str:
    if value is None or _safe_str(value) == "":
        return "-"
    dt = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(dt):
        return _safe_str(value)
    delta = datetime.now(timezone.utc) - dt.to_pydatetime()
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return str(mins) + "m ago"
    hours = mins // 60
    if hours < 24:
        return str(hours) + "h ago"
    return str(hours // 24) + "d ago"


def _build_queue_dataframe(batch_results: pd.DataFrame, customers_df: Optional[pd.DataFrame], role: str) -> pd.DataFrame:
    if batch_results is None or batch_results.empty:
        return pd.DataFrame(columns=_QUEUE_COLUMNS + ["customer_name_raw", "confidence_score", "confidence_tier", "notes"])

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
        rows.append(
            {
                "customer_id": customer_id,
                "customer_name_raw": raw_name or customer_id,
                "customer_name_display": display_name,
                "entity_type": _entity_label(_first_present(customer, "entity_type")),
                "confidence_score": score,
                "confidence_tier": _confidence_tier(score),
                "confidence_display": str(score) + " / " + _confidence_tier(score),
                "decision": _decision_label(_safe_str(result.get("disposition"))),
                "flags": ", ".join(flags) if flags else "-",
                "flag_count": len(flags),
                "last_updated": _format_ago(result.get("evaluation_date") or st.session_state.get("batch_run_at")),
                "notes": _build_notes(result, rule_ids),
                "disposition": _safe_str(result.get("disposition")).upper() or "REVIEW",
                "risk_rating": (_first_present(customer, "risk_rating") or "Unknown").title(),
                "jurisdiction": (_first_present(customer, "jurisdiction") or _safe_str(result.get("jurisdiction")) or "Unknown").upper(),
                "country_of_origin": _first_present(customer, "country_of_origin", "nationality"),
                "account_open_date": _format_date(_first_present(customer, "account_open_date", "open_date")),
                "last_kyc_review_date": _format_date(_first_present(customer, "last_kyc_review_date", "kyc_date")),
                "date_of_birth": _format_date(_first_present(customer, "date_of_birth", "dob")),
                "incorporation_date": _format_date(_first_present(customer, "incorporation_date", "registration_date")),
            }
        )

    return pd.DataFrame(rows)


def _result_lookup(batch_results: pd.DataFrame, customer_id: str) -> Dict[str, Any]:
    if batch_results is None or batch_results.empty:
        return {}
    rows = batch_results[batch_results["customer_id"].astype(str) == str(customer_id)]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def _run_dashboard_batch(user: Dict[str, Any], logger: Any, institution_id: Optional[str]) -> None:
    customers_df = st.session_state.get("customers_df")
    if customers_df is None or customers_df.empty:
        st.warning("Load customer data in Data & Documents before running the queue.")
        return

    customer_ids = customers_df["customer_id"].astype(str).tolist()
    batch_id = str(uuid.uuid4())[:8].upper()
    if logger:
        logger.log(
            "BATCH_RUN_START",
            batch_id=batch_id,
            details={
                "total": len(customer_ids),
                "initiated_by": user["username"],
                "institution_id": institution_id,
            },
        )

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    progress = st.progress(0.0)
    status = st.empty()

    for idx, customer_id in enumerate(customer_ids):
        try:
            result = st.session_state.kyc_engine.evaluate_customer(customer_id, institution_id=institution_id)
            if "ruleset_version" not in result:
                result["ruleset_version"] = get_active_ruleset_version()
            results.append(result)
        except Exception as exc:
            errors.append({"id": customer_id, "error": str(exc)})
        progress.progress((idx + 1) / max(len(customer_ids), 1))
        status.text(str(idx + 1) + "/" + str(len(customer_ids)))

    progress.empty()
    status.empty()

    rdf = pd.DataFrame(results)
    if rdf.empty:
        rdf = pd.DataFrame(
            columns=[
                "customer_id",
                "overall_score",
                "disposition",
                "rationale",
                "ruleset_version",
            ]
        )

    if "disposition" not in rdf.columns:
        if "expected_final_decision" in rdf.columns:
            rdf = rdf.rename(columns={"expected_final_decision": "disposition"})
        else:
            rdf["disposition"] = "REVIEW"
    if "overall_score" not in rdf.columns:
        rdf["overall_score"] = 0
    if "rationale" not in rdf.columns:
        rdf["rationale"] = "Awaiting engine scoring"
    if "ruleset_version" not in rdf.columns:
        rdf["ruleset_version"] = get_active_ruleset_version()

    for field in [col for col in rdf.columns if col.endswith("_score")]:
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
        flagged_ids = rdf[rdf["disposition"].isin(["REJECT", "REVIEW"])]["customer_id"].astype(str).tolist()
        logger.log(
            "BATCH_RUN_COMPLETE",
            batch_id=batch_id,
            details={
                "evaluated": len(results),
                "errors": len(errors),
                "reject": reject_count,
                "review": review_count,
                "pass_with_notes": int((rdf["disposition"] == "PASS_WITH_NOTES").sum()) if "disposition" in rdf.columns else 0,
                "pass": int((rdf["disposition"] == "PASS").sum()) if "disposition" in rdf.columns else 0,
                "avg_score": float(rdf["overall_score"].mean()) if "overall_score" in rdf.columns and len(rdf) else 0.0,
                "flagged_customer_ids": flagged_ids,
                "error_customer_ids": [item["id"] for item in errors],
                "ruleset_version": rdf["ruleset_version"].iloc[0] if "ruleset_version" in rdf.columns and len(rdf) else "unknown",
            },
        )

    st.rerun()


def _render_queue_metrics(queue_df: pd.DataFrame) -> None:
    total = len(queue_df)
    pass_count = int((queue_df["decision"] == "PASS").sum()) if total else 0
    fail_count = int((queue_df["decision"] == "FAIL").sum()) if total else 0
    high_risk = int(queue_df["risk_rating"].str.upper().isin(["HIGH", "CRITICAL"]).sum()) if total else 0
    review_count = int(queue_df["disposition"].isin(["REJECT", "REVIEW"]).sum()) if total else 0

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total Pass", pass_count)
        st.caption("of " + str(total) + " customers in scope")
    with m2:
        st.metric("Total Fail", fail_count)
        fail_rate = int(round((fail_count / total) * 100)) if total else 0
        st.caption(str(fail_rate) + "% fail rate")
    with m3:
        st.metric("High-Risk Customers", high_risk)
        st.caption(str(review_count) + " currently require review")


def _render_identity_module(queue_row: Dict[str, Any], result: Dict[str, Any], role: str) -> None:
    customer_id = queue_row["customer_id"]
    customers_df = st.session_state.get("customers_df")
    customer = _get_customer_row(customers_df, customer_id)
    id_row = _get_related_row(st.session_state.get("id_verifications"), customer_id)

    identity_rows = [
        {
            "Field": "Legal Name",
            "Value": queue_row["customer_id"]
            if queue_row["customer_name_raw"] == queue_row["customer_id"]
            else display_customer_name(queue_row["customer_name_raw"], role),
        },
        {"Field": "Customer ID", "Value": customer_id},
        {"Field": "Entity Type", "Value": queue_row["entity_type"]},
        {"Field": "Jurisdiction", "Value": queue_row["jurisdiction"]},
        {"Field": "Country of Origin", "Value": queue_row["country_of_origin"] or "-"},
        {"Field": "Risk Rating", "Value": queue_row["risk_rating"]},
    ]

    if queue_row["entity_type"] == "Corporate":
        identity_rows.append(
            {
                "Field": "Incorporation Date",
                "Value": queue_row["incorporation_date"],
            }
        )
    else:
        identity_rows.append(
            {
                "Field": "Date of Birth",
                "Value": mask(queue_row["date_of_birth"], "dob") if queue_row["date_of_birth"] != "-" else "-",
            }
        )

    identity_rows.extend(
        [
            {"Field": "Account Opened", "Value": queue_row["account_open_date"]},
            {"Field": "Last KYC Review", "Value": queue_row["last_kyc_review_date"]},
            {"Field": "ID Type", "Value": _entity_label(_first_present(id_row, "document_type")) if id_row else "-"},
            {
                "Field": "Document Number",
                "Value": mask(_first_present(id_row, "document_number", "document_id"), "account")
                if id_row
                else "-",
            },
            {"Field": "ID Expiry", "Value": _format_date(_first_present(id_row, "expiry_date")) if id_row else "-"},
            {
                "Field": "ID Verification",
                "Value": _first_present(id_row, "document_status", "verification_status").upper() or "-",
            },
            {
                "Field": "Ruleset Version",
                "Value": _safe_str(result.get("ruleset_version")) or get_active_ruleset_version(),
            },
        ]
    )

    st.markdown("#### Profile · Identity")
    st_dataframe_safe(pd.DataFrame(identity_rows), use_container_width=True, hide_index=True)


def _render_summary_module(queue_row: Dict[str, Any], result: Dict[str, Any]) -> None:
    rules = _extract_rule_ids(result)
    c1, c2, c3 = st.columns(3)
    c1.metric("Decision", queue_row["decision"])
    c2.metric("Confidence", str(queue_row["confidence_score"]) + "/100", queue_row["confidence_tier"])
    c3.metric("Flags", queue_row["flag_count"])

    st.markdown("#### Decision Summary")
    st.markdown("**Notes**")
    st.write(queue_row["notes"])

    if rules:
        st.markdown("**Triggered Rules**")
        for rule_id in rules:
            st.markdown("- " + rule_id)


def _render_dimension_module(result: Dict[str, Any]) -> None:
    rows = []
    for label, field in [
        ("AML Screening", "aml_screening_score"),
        ("Identity Verification", "identity_verification_score"),
        ("Account Activity", "account_activity_score"),
        ("Proof of Address", "proof_of_address_score"),
        ("Beneficial Ownership", "beneficial_ownership_score"),
        ("Data Quality", "data_quality_score"),
        ("Source of Wealth", "source_of_wealth_score"),
        ("CRS/FATCA", "crs_fatca_score"),
    ]:
        rows.append({"Dimension": label, "Score": round(_as_float(result.get(field)), 1)})
    st.markdown("#### Module Signals")
    st_dataframe_safe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _reload_engine_from_session_data() -> None:
    from kyc_engine.engine import KYCComplianceEngine

    filename_map = {
        "customers": "customers_clean.csv",
        "screenings": "screenings_clean.csv",
        "id_verifications": "id_verifications_clean.csv",
        "transactions": "transactions_clean.csv",
        "documents": "documents_clean.csv",
        "beneficial_ownership": "beneficial_ownership_clean.csv",
    }
    temp_dir = Path(tempfile.mkdtemp(prefix="kyc_ruleset_reload_"))

    for df_key, filename in filename_map.items():
        if df_key == "customers":
            df_value = st.session_state.get("customers_df", st.session_state.get("customers"))
        else:
            df_value = st.session_state.get(df_key)
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
    import kyc_audit.logger as audit_logger_module
    import kyc_dashboard.main as main_module
    import kyc_dashboard.state as state_module

    audit_logger_module.RULESET_VERSION = new_version
    main_module.RULESET_VERSION = new_version
    state_module.RULESET_VERSION = new_version


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

    draft = st.text_area(
        "Active ruleset JSON",
        key="dashboard_ruleset_editor_text",
        height=420,
    )

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
                st.session_state.batch_results = None
                st.session_state.batch_id = None
                st.session_state.batch_run_at = None
                st.session_state.dashboard_last_viewed_customer = None
                if logger:
                    logger.log(
                        "RULESET_UPDATED",
                        details={
                            "updated_by": user["username"],
                            "ruleset_version": new_version,
                            "ruleset_file": _RULESET_PATH.name,
                        },
                    )
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


def render(user: Dict[str, Any], role: str, logger: Any) -> None:
    st.markdown("## Dashboard")
    st.caption("KYC Operations review queue with profile drill-down.")

    if not st.session_state.get("engines_initialized"):
        st.warning("No data loaded yet. Use Data & Documents to load customer files before running the queue.")
        _render_admin_tools(user, role, logger)
        return

    institutions = _get_available_institutions()
    institution_labels = [label for _, label in institutions]
    configured = get_configured_institution()
    if configured and configured in [iid for iid, _ in institutions]:
        default_index = [iid for iid, _ in institutions].index(configured)
    else:
        default_index = 0

    h1, h2 = st.columns([3, 2])
    with h1:
        selected_label = st.selectbox(
            "Institution",
            institution_labels,
            index=default_index,
            key="dashboard_institution",
        )
    with h2:
        st.markdown("")
        st.markdown("")
        if st.button("Run Dashboard Queue", type="primary", use_container_width=True, key="dashboard_run_queue"):
            selected_institution_id = next((iid for iid, label in institutions if label == selected_label), "__none__")
            institution_id = None if selected_institution_id == "__none__" else selected_institution_id
            _run_dashboard_batch(user, logger, institution_id)

    if st.session_state.get("batch_results") is not None:
        st.caption(
            "Last sync "
            + str(st.session_state.get("batch_run_at", "-"))
            + " · batch "
            + str(st.session_state.get("batch_id", "-"))
        )
    else:
        st.info("Run the dashboard queue to populate customer decisions for review.")
        _render_admin_tools(user, role, logger)
        return

    batch_results = st.session_state.get("batch_results")
    customers_df = st.session_state.get("customers_df")
    queue_df = _build_queue_dataframe(batch_results, customers_df, role)
    if queue_df.empty:
        st.info("No customers are available in the current queue run.")
        _render_admin_tools(user, role, logger)
        return

    _render_queue_metrics(queue_df)
    st.divider()

    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    search_term = f1.text_input("Search", placeholder="Customer ID, name, jurisdiction", key="dashboard_search")
    entity_filter = f2.selectbox("Entity Type", ["All"] + sorted(queue_df["entity_type"].dropna().unique().tolist()), key="dashboard_entity_filter")
    confidence_filter = f3.selectbox("Confidence Tier", ["Any", "High", "Medium", "Low"], key="dashboard_confidence_filter")
    decision_filter = f4.selectbox("Decision", ["Any", "PASS", "FAIL"], key="dashboard_decision_filter")

    filtered_df = queue_df.copy()
    if search_term.strip():
        needle = search_term.strip().lower()
        filtered_df = filtered_df[
            filtered_df["customer_id"].str.lower().str.contains(needle, na=False)
            | filtered_df["customer_name_raw"].str.lower().str.contains(needle, na=False)
            | filtered_df["jurisdiction"].str.lower().str.contains(needle, na=False)
        ]
    if entity_filter != "All":
        filtered_df = filtered_df[filtered_df["entity_type"] == entity_filter]
    if confidence_filter != "Any":
        filtered_df = filtered_df[filtered_df["confidence_tier"] == confidence_filter]
    if decision_filter != "Any":
        filtered_df = filtered_df[filtered_df["decision"] == decision_filter]

    st.caption("Showing " + str(len(filtered_df)) + " of " + str(len(queue_df)) + " customers")

    if filtered_df.empty:
        st.info("No customers match the current filters.")
        _render_admin_tools(user, role, logger)
        return

    selected_customer_id = st.session_state.get("dashboard_selected_customer_id")
    queue_ids = filtered_df["customer_id"].astype(str).tolist()
    if selected_customer_id not in queue_ids:
        selected_customer_id = queue_ids[0]
        st.session_state.dashboard_selected_customer_id = selected_customer_id

    left_col, right_col = st.columns([3, 2], gap="large")

    with left_col:
        selected_customer_id = st.selectbox(
            "Open customer record",
            queue_ids,
            index=queue_ids.index(selected_customer_id),
            format_func=lambda cid: cid + " · " + filtered_df[filtered_df["customer_id"] == cid].iloc[0]["customer_name_display"],
            key="dashboard_selected_customer_widget",
        )
        st.session_state.dashboard_selected_customer_id = selected_customer_id

        display_df = filtered_df.copy()
        display_df = display_df[_QUEUE_COLUMNS].rename(
            columns={
                "customer_id": "ID",
                "customer_name_display": "Customer Name",
                "entity_type": "Entity Type",
                "confidence_display": "Confidence",
                "decision": "Decision",
                "flags": "Flags",
                "last_updated": "Last Updated",
            }
        )
        st_dataframe_safe(display_df, use_container_width=True, hide_index=True)

    selected_queue_row = filtered_df[filtered_df["customer_id"] == selected_customer_id].iloc[0].to_dict()
    selected_result = _result_lookup(batch_results, selected_customer_id)

    last_viewed = st.session_state.get("dashboard_last_viewed_customer")
    if last_viewed != selected_customer_id and logger:
        logger.log(
            "CUSTOMER_VIEW",
            customer_id=selected_customer_id,
            details={
                "tab": "dashboard",
                "ruleset_version": _safe_str(selected_result.get("ruleset_version")) or get_active_ruleset_version(),
            },
            snapshot={field: selected_result.get(field) for field in _SNAPSHOT_FIELDS if field in selected_result},
        )
        st.session_state.dashboard_last_viewed_customer = selected_customer_id

    with right_col:
        current_index = queue_ids.index(selected_customer_id)
        nav1, nav2, nav3 = st.columns([1, 3, 1])
        with nav1:
            if st.button("Previous", key="dashboard_prev_customer", use_container_width=True):
                st.session_state.dashboard_selected_customer_id = queue_ids[(current_index - 1) % len(queue_ids)]
                st.rerun()
        with nav2:
            st.caption("Record " + str(current_index + 1) + " of " + str(len(queue_ids)))
        with nav3:
            if st.button("Next", key="dashboard_next_customer", use_container_width=True):
                st.session_state.dashboard_selected_customer_id = queue_ids[(current_index + 1) % len(queue_ids)]
                st.rerun()

        st.markdown("### " + selected_queue_row["customer_name_display"])
        st.caption(
            selected_queue_row["customer_id"]
            + " · "
            + selected_queue_row["entity_type"]
            + " · "
            + selected_queue_row["jurisdiction"]
            + " · "
            + selected_queue_row["risk_rating"]
            + " risk"
        )

        _render_summary_module(selected_queue_row, selected_result)
        st.divider()
        _render_identity_module(selected_queue_row, selected_result, role)
        st.divider()
        _render_dimension_module(selected_result)

    _render_admin_tools(user, role, logger)
