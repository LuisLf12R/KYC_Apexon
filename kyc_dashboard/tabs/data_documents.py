"""
Unified Data & Documents tab — Phase 11C.

Replaces the separate Data Management (tab3) and Document OCR (tab4) tabs.
Routes uploaded files by type:
  - CSV/Excel/JSON → structured data ingestion (Mode A)
  - PDF/image/docx → document analysis with field extraction + customer linking (Mode B)

Uses proper render() function (architectural decision #14 — no TAB_CODE exec).
"""

import datetime
import base64
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


def _clear_batch_queue():
    """Clear Data & Documents uploader/session queue state."""
    for key in list(st.session_state.keys()):
        if (
            key.startswith("doc_type_hint_")
            or key.startswith("customer_hint_")
            or key.startswith("analyze_doc_")
            or key.startswith("sensitivity_override_")
            or key.startswith("ocr_correction_")
            or key.startswith("confirm_link_")
            or key.startswith("pick_other_")
            or key.startswith("manual_select_")
            or key.startswith("multi_select_")
            or key.startswith("confirm_multi_")
            or key.startswith("no_match_select_")
            or key.startswith("manual_link_")
        ):
            del st.session_state[key]


def _clear_document_analysis_cache():
    """Clear OCR/sensitivity/extraction caches for uploaded documents."""
    for key in list(st.session_state.keys()):
        if key.startswith("doc_extraction_") or key.startswith("doc_ocr_") or key.startswith("doc_sensitivity_"):
            del st.session_state[key]


def _fuzzy_match_customer(
    extracted_name: Optional[str],
    extracted_dob: Optional[str],
    customers_df: pd.DataFrame,
    threshold: float = 0.85,
) -> List[Tuple[str, str, float]]:
    """Fuzzy match extracted name (+ optional DOB) against loaded customers."""
    if not extracted_name or customers_df is None or customers_df.empty:
        return []

    matches: List[Tuple[str, str, float]] = []
    name_lower = extracted_name.strip().lower()

    for _, row in customers_df.iterrows():
        cust_id = str(row.get("customer_id", ""))
        cust_name = str(row.get("full_name", row.get("name", "")))
        if not cust_name:
            continue

        name_score = SequenceMatcher(None, name_lower, cust_name.strip().lower()).ratio()

        if extracted_dob and "date_of_birth" in row.index:
            cust_dob = str(row.get("date_of_birth", ""))
            if extracted_dob.strip() == cust_dob.strip():
                name_score = min(1.0, name_score + 0.1)

        if name_score >= threshold:
            matches.append((cust_id, cust_name, round(name_score, 3)))

    matches.sort(key=lambda x: x[2], reverse=True)
    return matches


def _classify_file(filename: str) -> str:
    """Classify uploaded file as 'structured' or 'document'."""
    lower = filename.lower()
    if lower.endswith((".csv", ".xlsx", ".xls", ".json", ".jsonl")):
        return "structured"
    if lower.endswith((".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".docx")):
        return "document"
    return "unknown"


def _extract_document_fields(
    text: str,
    filename: str,
    doc_type_hint: str,
    customer_hint: str,
) -> Tuple[str, Dict[str, Any], Dict[str, float], Dict[str, Any]]:
    """Run Claude extraction and return (document_type, extracted_fields, confidences, full_analysis)."""
    import anthropic as ac
    from kyc_dashboard.main import get_prompt, _extract_json_from_response

    cfg = get_prompt("kyc-analysis-v1.0")
    system = cfg.get("system", "Extract KYC fields with citations.") + " Today is " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d") + ". Evaluate all dates against this reference."
    tmpl = cfg.get("user_template", "{ocr_text}")
    mcfg = cfg.get("model_settings", {})
    msg = tmpl.replace("{doc_type}", doc_type_hint or "Other").replace("{customer_id}", customer_hint or "Not provided").replace("{ocr_text}", text[:3000])

    client = ac.Anthropic(api_key=__import__("os").getenv("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=mcfg.get("model", "claude-opus-4-20250514"),
        max_tokens=mcfg.get("max_tokens", 1500),
        system=system,
        messages=[{"role": "user", "content": msg}],
    )
    analysis = _extract_json_from_response(resp.content[0].text)

    extracted_fields: Dict[str, Any] = {}
    confidences: Dict[str, float] = {}

    for key, value in analysis.items():
        if key.endswith("_confidence"):
            field_name = key[:-11]
            try:
                confidences[field_name] = float(value)
            except Exception:
                continue
            continue
        if key.endswith("_citation") or key in (
            "meta",
            "compliance_flags",
            "risk_indicators",
            "discrepancies",
            "extraction_summary",
            "overall_confidence",
            "document_type",
        ):
            continue
        extracted_fields[key] = value

    doc_type = str(analysis.get("document_type", doc_type_hint or "other"))
    return doc_type, extracted_fields, confidences, analysis


def _render_structured_section(files):
    """Process structured files and load engine state, ported from Data Management flow."""
    from kyc_dashboard.main import (
        AUTO_DETECT,
        _collect_discrepancy_report,
        _seed_structured_provenance,
        load_engine,
        log,
        process_file,
        save_to_temp,
        st_dataframe_safe,
        touch,
    )

    st.subheader("Structured Data")
    if not st.button("Process Structured Files", type="primary", key="process_structured_files"):
        return

    touch()
    cleaned: Dict[str, pd.DataFrame] = {}
    proc_log: List[Dict[str, Any]] = []
    bar = st.progress(0)
    txt = st.empty()
    total = len(files)

    with st.spinner("Running data cleaning pipeline..."):
        for i, uploaded_file in enumerate(files):
            fn = uploaded_file.name
            txt.text("Processing " + fn + " (" + str(i + 1) + "/" + str(total) + ")")
            log("FILE_UPLOAD", details={"filename": fn, "size": uploaded_file.size, "type_selected": AUTO_DETECT})
            try:
                df, method, det_type, _ = process_file(uploaded_file, fn, AUTO_DETECT)
                if det_type in cleaned:
                    cleaned[det_type] = pd.concat([cleaned[det_type], df], ignore_index=True).drop_duplicates()
                else:
                    cleaned[det_type] = df
                proc_log.append(
                    {
                        "File": fn,
                        "Dataset type detected": det_type,
                        "Rows loaded": len(df),
                        "Method": "claude_structured" if method == "ocr+llm" else "fallback_pandas",
                        "Status": "OK",
                    }
                )
            except Exception as exc:
                proc_log.append(
                    {
                        "File": fn,
                        "Dataset type detected": "auto_detect",
                        "Rows loaded": 0,
                        "Method": "error",
                        "Status": "FAILED: " + str(exc)[:120],
                    }
                )
            bar.progress((i + 1) / total)

    bar.empty()
    txt.empty()

    if proc_log:
        proc_df = pd.DataFrame(proc_log)
        st_dataframe_safe(proc_df, use_container_width=True, hide_index=True)

    if not cleaned:
        st.error("No structured datasets were loaded.")
        return

    tmp_dir = save_to_temp(cleaned)
    engine, customers = load_engine(tmp_dir)
    if engine is None or customers is None or len(customers) == 0:
        st.warning("Engine could not initialize. Ensure customers dataset has a customer_id column.")
        return

    st.session_state.kyc_engine = engine
    st.session_state.customers_df = customers
    st.session_state.customers = customers.copy()
    st.session_state.id_verifications = engine.id_verifications.copy() if engine.id_verifications is not None else pd.DataFrame()
    st.session_state.documents = engine.documents.copy() if engine.documents is not None else pd.DataFrame()
    st.session_state.engines_initialized = True
    st.session_state.data_dir = tmp_dir
    st.session_state.batch_results = None
    st.session_state.data_source_label = "Uploaded & cleaned (" + ", ".join(cleaned.keys()) + ")"
    _seed_structured_provenance()
    st.session_state.latest_discrepancy_report = _collect_discrepancy_report()
    st.success("Engine loaded — " + str(len(customers)) + " customers ready.")
    st.success("Data loaded successfully. You can now run evaluations in the Individual or Batch tabs.")
    if not st.session_state.get("data_loaded_flag"):
        st.session_state["data_loaded_flag"] = True
        st.rerun()


def _render_document_section(files):
    """Process document files with OCR, sensitivity checks, extraction, and customer linking."""
    from kyc_dashboard.main import LOW_CONFIDENCE_THRESHOLD, log, mask, run_ocr, touch
    from kyc_dashboard.provenance import (
        collect_discrepancies,
        get_provenance_store,
        record_ocr_provenance,
        update_customer_records,
    )
    from kyc_engine.document_sensitivity import (
        detect_sensitivity,
        requires_review,
        sensitivity_summary,
        should_block,
    )

    st.subheader("Document Analysis")

    tab_labels = [f.name for f in files]
    doc_tabs = st.tabs(tab_labels)

    for i, (tab, uploaded_file) in enumerate(zip(doc_tabs, files)):
        with tab:
            uploaded_file.seek(0)
            fbytes = uploaded_file.read()
            if not fbytes:
                st.warning("Could not read file bytes for " + uploaded_file.name)
                continue

            file_cache_key = uploaded_file.name
            ocr_cache_key = "doc_ocr_" + file_cache_key
            sens_cache_key = "doc_sensitivity_" + file_cache_key
            extraction_cache_key = "doc_extraction_" + file_cache_key

            if ocr_cache_key in st.session_state:
                text = st.session_state[ocr_cache_key]
            else:
                try:
                    with st.spinner("📝 Extracting text from document..."):
                        text = run_ocr(fbytes, uploaded_file.name)
                    st.session_state[ocr_cache_key] = text
                except Exception as exc:
                    st.error("OCR failed for " + uploaded_file.name + ": " + str(exc))
                    continue
            if text is None or not text.strip():
                st.warning("Could not extract text from " + uploaded_file.name)
                continue

            if sens_cache_key in st.session_state:
                sensitivity_flags = st.session_state[sens_cache_key]
            else:
                sensitivity_flags = detect_sensitivity(text)
                st.session_state[sens_cache_key] = sensitivity_flags

            if sensitivity_flags:
                summary = sensitivity_summary(sensitivity_flags)
                if isinstance(summary, dict):
                    categories = summary.get("categories", []) or []
                    cat_str = ", ".join(str(c) for c in categories) if categories else "Unknown"
                    st.markdown("**Sensitivity:** " + cat_str + " detected")
                    messages = [str(f.get("message", "")).strip() for f in summary.get("flags", []) if isinstance(f, dict)]
                    if messages:
                        st.caption(messages[0])
                else:
                    st.markdown("**Sensitivity:** " + str(summary))
                if should_block(sensitivity_flags):
                    st.error(
                        "This document contains SAMPLE or SPECIMEN markers, which typically means "
                        "it is not an original document and should not be used for compliance verification."
                    )
                    st.markdown(
                        "If you believe this is a legitimate document incorrectly flagged, "
                        "you can override the block by providing a justification below. "
                        "This will be logged in the audit trail."
                    )
                    override_reason = st.text_input(
                        "Justification to proceed despite SAMPLE flag:",
                        key="sensitivity_override_" + str(i),
                        placeholder="e.g., 'Verified with issuer — watermark is from scanning process'",
                    )
                    if not override_reason:
                        st.warning("Provide justification to continue analysis for this blocked document.")
                        continue
                    st.info("Override accepted: " + override_reason)
                elif requires_review(sensitivity_flags):
                    st.warning("This document has sensitivity flags. Proceeding with analysis.")
            else:
                st.markdown("**Sensitivity:** None detected")

            doc_type_hint = st.selectbox(
                "Document Type",
                [
                    "drivers_license",
                    "passport",
                    "national_id",
                    "utility_bill",
                    "bank_statement",
                    "credit_report",
                    "other",
                ],
                key="doc_type_hint_" + str(i),
            )
            customer_hint = st.text_input("Customer ID Hint (optional)", key="customer_hint_" + str(i))

            analyze_clicked = st.button("Analyze " + uploaded_file.name, key="analyze_doc_" + str(i))
            if extraction_cache_key in st.session_state:
                cached = st.session_state[extraction_cache_key]
                document_type = cached["document_type"]
                extracted_fields = dict(cached["extracted_fields"])
                confidences = dict(cached["confidences"])
                analysis = dict(cached["analysis"])
            elif analyze_clicked:
                touch()
                log("LLM_CALL", details={"filename": uploaded_file.name, "doc_type": doc_type_hint})
                try:
                    with st.spinner("🔍 AI Agent analyzing document — extracting fields and assessing confidence..."):
                        document_type, extracted_fields, confidences, analysis = _extract_document_fields(
                            text,
                            uploaded_file.name,
                            doc_type_hint,
                            customer_hint,
                        )
                    st.session_state[extraction_cache_key] = {
                        "document_type": document_type,
                        "extracted_fields": dict(extracted_fields),
                        "confidences": dict(confidences),
                        "analysis": dict(analysis),
                    }
                except Exception as exc:
                    st.error("AI analysis failed: " + str(exc))
                    continue
            else:
                continue

            conf = float(analysis.get("overall_confidence", 0) or 0)
            m1, m2, m3 = st.columns(3)
            m1.metric("Document Type", analysis.get("document_type", "Unknown"))
            m2.metric("Confidence", str(int(conf * 100)) + "%")
            m3.metric("Flags", len(analysis.get("compliance_flags", [])))

            if conf < LOW_CONFIDENCE_THRESHOLD:
                st.warning(
                    "Confidence "
                    + str(int(conf * 100))
                    + "% is below the "
                    + str(int(LOW_CONFIDENCE_THRESHOLD * 100))
                    + "% threshold. Auto-flagged for mandatory human review."
                )

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
                val = analysis.get(key)
                conf_val = float(analysis.get(key + "_confidence", confidences.get(key, 0)) or 0)
                extracted_rows.append(
                    {
                        "field_key": key,
                        "Field": label,
                        "Extracted value": mask(val, mask_type) if val else "Not found",
                        "Confidence": conf_val,
                    }
                )

            corrected_values: Dict[str, Any] = {}
            st.markdown("#### Extracted Fields")
            st.dataframe(pd.DataFrame(extracted_rows)[["Field", "Extracted value", "Confidence"]], use_container_width=True, hide_index=True)

            low_conf_fields = [row for row in extracted_rows if row["Confidence"] < 0.75]
            if low_conf_fields:
                st.warning("Low-confidence fields detected (<75%). Review and correct before linking.")
                for low in low_conf_fields:
                    field_key = low["field_key"]
                    corrected_values[field_key] = st.text_input(
                        low["Field"] + " (correction)",
                        value=str(analysis.get(field_key) or ""),
                        key="ocr_correction_" + str(i) + "_" + field_key,
                    )

            for field_key, corrected_value in corrected_values.items():
                extracted_fields[field_key] = corrected_value
                try:
                    confidences[field_key] = 1.0
                except Exception:
                    pass

            with st.expander("Preview Original Document", expanded=False):
                filename_lower = uploaded_file.name.lower()
                if filename_lower.endswith((".png", ".jpg", ".jpeg", ".tiff")):
                    st.image(fbytes, caption=uploaded_file.name, use_container_width=True)
                elif filename_lower.endswith(".pdf"):
                    b64 = base64.b64encode(fbytes).decode("utf-8")
                    pdf_display = (
                        '<iframe src="data:application/pdf;base64,' + b64 + '" '
                        'width="100%" height="600" type="application/pdf"></iframe>'
                    )
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    st.download_button(
                        "Download PDF",
                        data=fbytes,
                        file_name=uploaded_file.name,
                        mime="application/pdf",
                        key="preview_download_" + str(i),
                    )
                elif filename_lower.endswith(".docx"):
                    st.caption("Word document preview not available. Use the extracted fields above or download to verify.")
                    st.download_button(
                        "Download .docx to view",
                        data=fbytes,
                        file_name=uploaded_file.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="preview_download_docx_" + str(i),
                    )
                else:
                    st.caption("Preview not available for this file type.")

            customers_df = st.session_state.get("customers", st.session_state.get("customers_df", None))
            if customers_df is None or getattr(customers_df, "empty", True):
                st.info("No customer data loaded. Upload a customers CSV first to enable linking.")
                continue

            extracted_name = None
            extracted_dob = None
            for name_key in ["full_name", "name", "customer_name", "Name"]:
                if name_key in extracted_fields and str(extracted_fields.get(name_key, "")).strip():
                    extracted_name = str(extracted_fields[name_key])
                    break
            for dob_key in ["date_of_birth", "dob", "DOB", "Date of Birth"]:
                if dob_key in extracted_fields and str(extracted_fields.get(dob_key, "")).strip():
                    extracted_dob = str(extracted_fields[dob_key])
                    break

            matches = _fuzzy_match_customer(extracted_name, extracted_dob, customers_df)
            selected_customer_id = None

            if len(matches) == 1 and matches[0][2] > 0.85:
                cid, cname, score = matches[0]
                st.markdown("🔗 **Customer match:** " + cid + " (" + cname + ") — " + str(int(score * 100)) + "%")
                c1, c2 = st.columns(2)
                if c1.button("Confirm & Link", key="confirm_link_" + str(i)):
                    selected_customer_id = cid
                if c2.button("Pick different customer", key="pick_other_" + str(i)):
                    selected_customer_id = st.selectbox(
                        "Select customer:",
                        customers_df["customer_id"].astype(str).tolist(),
                        key="manual_select_" + str(i),
                    )
            elif len(matches) > 1:
                st.markdown("🔗 **Multiple customer matches found:**")
                options = [cid + " (" + cname + ") — " + str(int(score * 100)) + "%" for cid, cname, score in matches]
                choice = st.selectbox("Select customer to link:", options, key="multi_select_" + str(i))
                if st.button("Confirm & Link", key="confirm_multi_" + str(i)):
                    selected_customer_id = matches[options.index(choice)][0]
            else:
                st.markdown("🔗 **No customer match found.**")
                all_cids = customers_df["customer_id"].astype(str).tolist()
                manual = st.selectbox("Select customer manually:", ["(skip)"] + all_cids, key="no_match_select_" + str(i))
                if manual != "(skip)" and st.button("Link to selected customer", key="manual_link_" + str(i)):
                    selected_customer_id = manual

            if not selected_customer_id:
                continue

            eval_key = "last_evaluation_" + selected_customer_id
            if eval_key not in st.session_state:
                try:
                    engine_for_snapshot = st.session_state.get("kyc_engine")
                    if engine_for_snapshot is not None:
                        snapshot = engine_for_snapshot.evaluate_customer(selected_customer_id)
                        st.session_state[eval_key] = _result_to_dict(snapshot)
                except Exception:
                    pass

            store = get_provenance_store()
            record_ocr_provenance(
                store=store,
                customer_id=selected_customer_id,
                extracted_fields=extracted_fields,
                source_file=uploaded_file.name,
                confidences=confidences,
            )

            discs = collect_discrepancies(store, selected_customer_id)
            if discs:
                st.warning("⚠️ Discrepancies detected:")
                for disc in discs:
                    st.markdown(
                        "- **"
                        + disc.field_name
                        + "**: existing = `"
                        + str(disc.existing_value)
                        + "` ("
                        + disc.existing_source
                        + ") vs new = `"
                        + str(disc.new_value)
                        + "` ("
                        + disc.new_source
                        + ")"
                    )

            engine = st.session_state.get("kyc_engine")
            current_dfs: Dict[str, pd.DataFrame] = {}
            for df_key in ["id_verifications", "documents", "customers"]:
                if df_key in st.session_state and isinstance(st.session_state[df_key], pd.DataFrame):
                    current_dfs[df_key] = st.session_state[df_key]
                elif engine is not None and hasattr(engine, df_key):
                    df_val = getattr(engine, df_key)
                    if isinstance(df_val, pd.DataFrame):
                        current_dfs[df_key] = df_val

            if current_dfs:
                updated_dfs = update_customer_records(current_dfs, selected_customer_id, document_type, extracted_fields)
                for df_key, df_val in updated_dfs.items():
                    st.session_state[df_key] = df_val
                    if engine is not None and hasattr(engine, df_key):
                        setattr(engine, df_key, df_val)
                if "customers" in updated_dfs:
                    st.session_state.customers_df = updated_dfs["customers"].copy()

            st.success("✅ Document linked to " + selected_customer_id)
            _render_remediation_preview(selected_customer_id)


def _result_to_dict(result: Any) -> Dict[str, Any]:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return {}


def _extract_rule_ids(result: Dict[str, Any]) -> set:
    ids = set()
    for key in ["triggered_rules", "triggered_reject_rules", "triggered_review_rules"]:
        items = result.get(key, []) or []
        for item in items:
            if isinstance(item, dict):
                rid = str(item.get("rule_id", item.get("id", ""))).strip()
            elif hasattr(item, "rule_id"):
                rid = str(getattr(item, "rule_id", "")).strip()
            else:
                rid = str(item).strip()
            if rid:
                ids.add(rid)
    return ids


def _render_remediation_preview(selected_customer_id: str):
    st.markdown("---")
    st.subheader("Remediation Preview")

    try:
        import os
        import tempfile
        from kyc_engine.engine import KYCComplianceEngine

        filename_map = {
            "customers": "customers_clean.csv",
            "screenings": "screenings_clean.csv",
            "id_verifications": "id_verifications_clean.csv",
            "transactions": "transactions_clean.csv",
            "documents": "documents_clean.csv",
            "beneficial_ownership": "beneficial_ownership_clean.csv",
        }
        numeric_columns = [
            "overall_score",
            "aml_screening_score",
            "identity_verification_score",
            "account_activity_score",
            "proof_of_address_score",
            "beneficial_ownership_score",
            "data_quality_score",
            "source_of_wealth_score",
            "crs_fatca_score",
            "transaction_amount",
            "amount",
            "txn_count",
            "total_volume",
            "ownership_percentage",
            "ownership_percent",   # actual column name read by BeneficialOwnershipDimension
            "ownership_pct",
            "parent_ownership_pct",
        ]

        temp_dir = tempfile.mkdtemp(prefix="kyc_preview_")
        for df_key, filename in filename_map.items():
            df_val = st.session_state.get(df_key)
            if df_val is None and df_key == "customers":
                df_val = st.session_state.get("customers_df")
            if isinstance(df_val, pd.DataFrame):
                df_copy = df_val.copy()
                for col in numeric_columns:
                    if col in df_copy.columns:
                        df_copy[col] = pd.to_numeric(df_copy[col], errors="coerce").fillna(0.0)
                df_copy.to_csv(os.path.join(temp_dir, filename), index=False)

        eval_key = "last_evaluation_" + selected_customer_id
        before_result = _result_to_dict(st.session_state.get(eval_key))

        try:
            preview_engine = KYCComplianceEngine(data_clean_dir=temp_dir)
            after_raw = preview_engine.evaluate_customer(selected_customer_id)
            after_result = _result_to_dict(after_raw)
        except (TypeError, ValueError) as exc:
            st.warning(
                "Remediation preview encountered a type error during re-evaluation. "
                "This usually means a numeric field was stored as text. Error: " + str(exc)
            )
            return

        if not after_result:
            st.warning("Could not evaluate customer " + selected_customer_id + " — engine may not have enough data.")
            return

        if before_result:
            before_disposition = str(before_result.get("disposition", "UNKNOWN"))
            after_disposition = str(after_result.get("disposition", "UNKNOWN"))
            before_rules = _extract_rule_ids(before_result)
            after_rules = _extract_rule_ids(after_result)

            resolved_rules = sorted(before_rules - after_rules)
            remaining_rules = sorted(after_rules)
            new_rules = sorted(after_rules - before_rules)

            if resolved_rules:
                for rule_id in resolved_rules:
                    st.markdown("✅ **Resolved:** " + rule_id)
            if remaining_rules:
                for rule_id in remaining_rules:
                    st.markdown("⚠️ **Remaining:** " + rule_id)
            if new_rules:
                for rule_id in new_rules:
                    st.markdown("🆕 **New flag:** " + rule_id)

            if before_disposition != after_disposition:
                st.success("Disposition change: " + before_disposition + " → " + after_disposition)
            else:
                st.info("Disposition unchanged: " + after_disposition)
        else:
            after_disposition = str(after_result.get("disposition", "UNKNOWN"))
            st.info("Current disposition after linking: " + after_disposition)
            after_rules = sorted(_extract_rule_ids(after_result))
            if after_rules:
                st.markdown("**Active flags:**")
                for rule_id in after_rules:
                    st.markdown("- " + rule_id)

        st.session_state[eval_key] = after_result
    except Exception as exc:
        st.warning("Remediation preview unavailable: " + str(exc))


def render(user=None, role=None, logger=None):
    """Render the unified Data & Documents tab."""
    st.header("Data & Documents")
    st.caption("Upload structured data files (CSV, Excel, JSON) or documents (PDF, images, Word) for analysis and customer linking.")

    if "uploader_key_counter" not in st.session_state:
        st.session_state["uploader_key_counter"] = 0
    uploader_key = "data_documents_uploader_" + str(st.session_state["uploader_key_counter"])

    col_upload, col_clear = st.columns([6, 1])
    with col_upload:
        uploaded_files = st.file_uploader(
            "Upload Files",
            type=["csv", "xlsx", "xls", "json", "jsonl", "pdf", "png", "jpg", "jpeg", "tiff", "docx"],
            accept_multiple_files=True,
            key=uploader_key,
        )
    with col_clear:
        st.markdown("")
        st.markdown("")
        if st.button("🗑️ Clear All", key="clear_all_uploads"):
            st.session_state["uploader_key_counter"] += 1
            _clear_batch_queue()
            _clear_document_analysis_cache()
            st.rerun()

    if not uploaded_files:
        st.info("Upload files to get started. You can mix structured data files and documents in a single upload.")
        return

    upload_key = "batch_processed_" + "_".join(sorted(f.name for f in uploaded_files))
    if st.session_state.get("last_upload_key") != upload_key:
        _clear_document_analysis_cache()
        st.session_state["last_upload_key"] = upload_key

    structured_files = []
    document_files = []
    unknown_files = []
    for uploaded_file in uploaded_files:
        ftype = _classify_file(uploaded_file.name)
        if ftype == "structured":
            structured_files.append(uploaded_file)
        elif ftype == "document":
            document_files.append(uploaded_file)
        else:
            unknown_files.append(uploaded_file)

    if unknown_files:
        st.warning("Unsupported file types (skipped): " + ", ".join(f.name for f in unknown_files))

    if structured_files:
        _render_structured_section(structured_files)

    if document_files:
        _render_document_section(document_files)
