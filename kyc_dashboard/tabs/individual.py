from pathlib import Path

from kyc_dashboard.components import get_configured_institution


def _get_available_institutions():
    """Return list of (institution_id, display_label) from rules/institutions/."""
    import json

    inst_dir = Path("rules/institutions")
    institutions = [("__none__", "None (jurisdiction defaults)")]
    if not inst_dir.exists():
        return institutions

    for f in sorted(inst_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            iid = data.get("institution_id", f.stem)
            name = data.get("institution_name", data.get("name", iid))
            active = data.get("active", True)
            label = f"{name} ({iid})" if name != iid else iid
            if not active:
                label += " [inactive]"
            institutions.append((iid, label))
        except Exception:
            continue

    return institutions


TAB_CODE = """touch()
if not st.session_state.engines_initialized:
    st.warning("No data loaded. Go to the Data Management tab to upload files.")
else:
    st.markdown("### Search & Evaluate Customer")

    cid_input = st.text_input("Customer ID", placeholder="C00001",
                               label_visibility="collapsed")
    institutions = _get_available_institutions()
    institution_labels = [label for _, label in institutions]
    configured = get_configured_institution()
    if configured and configured in [iid for iid, _ in institutions]:
        default_index = [iid for iid, _ in institutions].index(configured)
    else:
        default_index = 0
    selected_institution_label = st.selectbox("Institution", institution_labels, index=default_index)
    selected_institution_id = next(
        (iid for iid, label in institutions if label == selected_institution_label),
        "__none__"
    )
    eval_btn = st.button("Evaluate Customer", type="primary", use_container_width=True)

    if eval_btn and cid_input:
        cid = cid_input.strip().upper()
        touch()
        with st.spinner(f"Evaluating {cid}..."):
            try:
                institution_id = None if selected_institution_id == "__none__" else selected_institution_id
                result = st.session_state.kyc_engine.evaluate_customer(cid, institution_id=institution_id)
                disposition   = result.get("disposition", "REVIEW")
                score         = result.get("overall_score", 0)
                rationale     = result.get("rationale", "")
                reject_rules  = result.get("triggered_reject_rules", [])
                review_rules  = result.get("triggered_review_rules", [])
                ruleset_ver   = result.get("ruleset_version", "unknown")

                log("CUSTOMER_VIEW", customer_id=cid,
                    details={"tab": "individual_evaluation", "ruleset_version": ruleset_ver},
                    snapshot={k: result.get(k) for k in [
                        "overall_score", "disposition",
                        "aml_screening_score", "identity_verification_score",
                        "account_activity_score", "proof_of_address_score",
                        "beneficial_ownership_score", "data_quality_score",
                    ]})

                if disposition in ("REJECT", "REVIEW"):
                    log("FLAG_RAISED", customer_id=cid,
                        details={"disposition": disposition, "score": score,
                                 "triggered_rules": [r["rule_id"] for r in reject_rules + review_rules]})

                history_entry = {
                    "timestamp":                  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "evaluated_by":               user["username"],
                    "overall_score":              score,
                    "disposition":                disposition,
                    "aml_screening_score":        result.get("aml_screening_score", 0),
                    "identity_verification_score":result.get("identity_verification_score", 0),
                    "account_activity_score":     result.get("account_activity_score", 0),
                    "proof_of_address_score":     result.get("proof_of_address_score", 0),
                    "beneficial_ownership_score": result.get("beneficial_ownership_score", 0),
                    "data_quality_score":         result.get("data_quality_score", 0),
                }
                if cid not in st.session_state.customer_history:
                    st.session_state.customer_history[cid] = []
                st.session_state.customer_history[cid].append(history_entry)

                # ── Pre-compute dimension data ─────────────────────────────────
                dim_map = [
                    ("aml_screening",         "AML Screening",         25),
                    ("identity_verification", "Identity Verification", 20),
                    ("account_activity",      "Account Activity",      15),
                    ("proof_of_address",      "Proof of Address",      15),
                    ("beneficial_ownership",  "Beneficial Ownership",  15),
                    ("data_quality",          "Data Quality",          10),
                ]
                passing, minor_gaps, failing = [], [], []
                for dk, dlabel, dweight in dim_map:
                    ds = result.get(f"{dk}_score", 0)
                    dfinding = result.get(f"{dk}_details", {}).get("finding", "N/A")
                    entry = {"label": dlabel, "score": ds, "weight": dweight, "finding": dfinding}
                    if ds >= 70:
                        passing.append(entry)
                    elif ds >= 50:
                        minor_gaps.append(entry)
                    else:
                        failing.append(entry)

                n_reject_rules  = len(reject_rules)
                n_review_rules  = len(review_rules)
                n_failing       = len(failing)
                n_minor         = len(minor_gaps)
                total_evals     = len(st.session_state.customer_history.get(cid, []))
                selected_inst_display = institution_id if institution_id is not None else "None (jurisdiction defaults)"

                # ── Dashboard Header: 3-column layout ──────────────────────────
                hcol_l, hcol_c, hcol_r = st.columns([2.5, 2, 2.5])

                with hcol_c:
                    gauge_color = (COLORS["compliant"]     if score >= 70
                                   else COLORS["minor"]    if score >= 50
                                   else COLORS["non_compliant"])
                    gauge_fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=score,
                        number={"suffix": "/100", "font": {"size": 28}},
                        gauge={
                            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "gray"},
                            "bar":  {"color": gauge_color, "thickness": 0.3},
                            "bgcolor": "rgba(0,0,0,0)",
                            "steps": [
                                {"range": [0, 50],   "color": "rgba(213,94,0,0.12)"},
                                {"range": [50, 70],  "color": "rgba(230,159,0,0.12)"},
                                {"range": [70, 100], "color": "rgba(0,158,115,0.12)"},
                            ],
                            "threshold": {
                                "line": {"color": gauge_color, "width": 3},
                                "thickness": 0.75,
                                "value": score,
                            },
                        },
                        title={"text": "Overall Score", "font": {"size": 14}},
                    ))
                    gauge_fig.update_layout(
                        height=230,
                        margin=dict(l=20, r=20, t=30, b=10),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(gauge_fig, use_container_width=True)

                with hcol_l:
                    st.markdown("<div style='padding-top:12px'></div>", unsafe_allow_html=True)
                    show_disposition(disposition)
                    st.markdown(f"**Customer ID:** `{cid}`")
                    st.markdown(f"**Institution:** {selected_inst_display}")
                    st.markdown(f"**Ruleset:** {ruleset_ver}")
                    st.markdown(f"**Rationale:** {rationale}")

                with hcol_r:
                    st.markdown("<div style='padding-top:16px'></div>", unsafe_allow_html=True)
                    rc_reject = COLORS["non_compliant"] if n_reject_rules else "gray"
                    rc_review = COLORS["minor"]         if n_review_rules else "gray"
                    rc_fail   = COLORS["non_compliant"] if n_failing      else "gray"
                    rc_minor  = COLORS["minor"]         if n_minor        else "gray"
                    st.markdown(
                        "<div style='background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:16px'>"
                        "<div style='font-size:11px;color:gray;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px'>Risk Indicators</div>"
                        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
                        f"<span style='font-size:13px'>Hard Reject Rules</span>"
                        f"<span style='font-size:18px;font-weight:700;color:{rc_reject}'>{n_reject_rules}</span></div>"
                        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
                        f"<span style='font-size:13px'>Review Rules Triggered</span>"
                        f"<span style='font-size:18px;font-weight:700;color:{rc_review}'>{n_review_rules}</span></div>"
                        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
                        f"<span style='font-size:13px'>Failing Dimensions</span>"
                        f"<span style='font-size:18px;font-weight:700;color:{rc_fail}'>{n_failing}</span></div>"
                        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
                        f"<span style='font-size:13px'>Minor Gaps</span>"
                        f"<span style='font-size:18px;font-weight:700;color:{rc_minor}'>{n_minor}</span></div>"
                        "<div style='border-top:1px solid rgba(255,255,255,0.08);padding-top:8px;margin-top:4px;"
                        "display:flex;justify-content:space-between;align-items:center'>"
                        f"<span style='font-size:13px;color:gray'>Session Evaluations</span>"
                        f"<span style='font-size:14px;color:gray'>{total_evals}</span></div>"
                        "</div>",
                        unsafe_allow_html=True
                    )

                st.divider()

                # ── Triggered Rules ─────────────────────────────────────────────
                if reject_rules:
                    st.markdown("**Hard Rejection Rules Triggered:**")
                    for r in reject_rules:
                        st.markdown(
                            f"<div style='border-left:4px solid {COLORS['non_compliant']};"
                            "padding:8px 12px;margin:4px 0;"
                            "background:rgba(213,94,0,0.08);border-radius:4px'>"
                            f"<strong>{r['rule_id']} — {r['name']}</strong><br>"
                            f"<span style='color:gray;font-size:13px'>{r['description']}</span><br>"
                            f"<span style='color:gray;font-size:12px'>Policy: {r['policy_reference']}</span>"
                            "</div>",
                            unsafe_allow_html=True
                        )

                if review_rules:
                    st.markdown("**Review Rules Triggered:**")
                    for r in review_rules:
                        st.markdown(
                            f"<div style='border-left:4px solid {COLORS['minor']};"
                            "padding:8px 12px;margin:4px 0;"
                            "background:rgba(230,159,0,0.08);border-radius:4px'>"
                            f"<strong>{r['rule_id']} — {r['name']}</strong><br>"
                            f"<span style='color:gray;font-size:13px'>{r['description']}</span><br>"
                            f"<span style='color:gray;font-size:12px'>Policy: {r['policy_reference']}</span>"
                            "</div>",
                            unsafe_allow_html=True
                        )

                st.divider()

                # ── Dimension Score Cards (failing first, then minor, then passing) ──
                st.markdown("#### Dimension Scores")
                dcols = st.columns(3)
                dims_display = failing + minor_gaps + passing
                for i, e in enumerate(dims_display):
                    sd = e["score"]
                    if sd >= 70:
                        bcolor      = COLORS["compliant"]
                        status_lbl  = "PASS"
                        bg_card     = "rgba(0,158,115,0.07)"
                    elif sd >= 50:
                        bcolor      = COLORS["minor"]
                        status_lbl  = "REVIEW"
                        bg_card     = "rgba(230,159,0,0.07)"
                    else:
                        bcolor      = COLORS["non_compliant"]
                        status_lbl  = "FAIL"
                        bg_card     = "rgba(213,94,0,0.07)"
                    finding_raw   = e["finding"]
                    finding_short = finding_raw[:90] + ("..." if len(finding_raw) > 90 else "")
                    with dcols[i % 3]:
                        st.markdown(
                            f"<div style='border:1px solid {bcolor};border-radius:10px;"
                            f"padding:14px 16px;margin-bottom:12px;background:{bg_card}'>"
                            "<div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:2px'>"
                            f"<span style='font-weight:600;font-size:13px'>{e['label']}</span>"
                            f"<span style='font-size:10px;font-weight:700;color:{bcolor};"
                            "background:rgba(0,0,0,0.2);padding:2px 7px;border-radius:10px'>"
                            f"{status_lbl}</span>"
                            "</div>"
                            f"<div style='font-size:10px;color:gray;margin-bottom:8px'>Weight: {e['weight']}%</div>"
                            "<div style='display:flex;align-items:baseline;gap:4px;margin-bottom:8px'>"
                            f"<span style='font-size:28px;font-weight:700;color:{bcolor};line-height:1'>{sd}</span>"
                            "<span style='font-size:12px;color:gray'>/100</span>"
                            "</div>"
                            "<div style='background:rgba(255,255,255,0.08);border-radius:4px;height:6px;margin-bottom:8px'>"
                            f"<div style='width:{sd}%;height:100%;background:{bcolor};border-radius:4px'></div>"
                            "</div>"
                            "<div style='font-size:11px;color:rgba(255,255,255,0.55);"
                            "border-top:1px solid rgba(255,255,255,0.06);padding-top:6px'>"
                            f"{finding_short}</div>"
                            "</div>",
                            unsafe_allow_html=True
                        )

                # ── Provenance ──────────────────────────────────────────────────
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
                            field    = d.get("field_name", "")
                            vals     = d.get("values_by_source", {})
                            user_val = vals.get("User-Provided", {}).get("value")
                            ocr_val  = vals.get("OCR-Extracted", {}).get("value")
                            ocr_file = vals.get("OCR-Extracted", {}).get("source_file", "")
                            ocr_conf = _format_conf_pct(vals.get("OCR-Extracted", {}).get("confidence"))
                            st.markdown(
                                f"- **{field}**: User-Provided='{user_val}' vs OCR-Extracted='{ocr_val}' "
                                f"(from {ocr_file or 'N/A'}, {ocr_conf or 'N/A'} confidence)"
                            )

                # ── Remediation ─────────────────────────────────────────────────
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

                # ── Evaluation History Trend ────────────────────────────────────
                history = st.session_state.customer_history.get(cid, [])
                if len(history) > 1:
                    st.divider()
                    st.markdown("#### Evaluation History — This Session")
                    st_dataframe_safe(pd.DataFrame(history), use_container_width=True, hide_index=True)
                    scores_h     = [h["overall_score"] for h in history]
                    timestamps_h = [h["timestamp"]     for h in history]
                    fig2 = go.Figure(go.Scatter(
                        x=timestamps_h, y=scores_h, mode="lines+markers",
                        marker=dict(size=8, color=COLORS["blue"]),
                        line=dict(color=COLORS["blue"]),
                    ))
                    fig2.update_layout(
                        title=f"Score Trend — {cid}",
                        yaxis=dict(range=[0, 110]),
                        height=220,
                        margin=dict(l=10, r=10, t=40, b=10),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            except Exception as e:
                st.error(f"Evaluation error: {e}")
"""


def render(user, role, logger):
    import kyc_dashboard.main as a

    ns = dict(a.__dict__)
    ns.update({'user': user, 'role': role, 'logger': logger})
    ns["_get_available_institutions"] = _get_available_institutions
    ns["get_configured_institution"] = get_configured_institution
    exec(TAB_CODE, ns, ns)
