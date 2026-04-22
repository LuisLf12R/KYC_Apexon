"""
kyc_dashboard/tabs/impact_analysis.py
P7-G — Change-impact analysis surface.

Lets an analyst pick a staged jurisdiction overlay, run compute_impact()
against current engine decisions for that jurisdiction's customers, and
see which decisions would flip disposition before the merge is approved.
"""

import streamlit as st
import pandas as pd

from kyc_dashboard.state import touch, log


def render(user, role, logger):
    touch()
    st.subheader("📊 Change-Impact Analysis")
    st.caption(
        "Preview which customer dispositions would change if a staged overlay "
        "were merged — without re-running the full engine or touching live data."
    )

    # ── Guard: engine must be loaded ─────────────────────────────────────────
    if not st.session_state.get("engines_initialized"):
        st.warning("Load customer data in **Data Management** before running impact analysis.")
        return

    engine = st.session_state.kyc_engine

    # ── Load staged overlays ──────────────────────────────────────────────────
    try:
        from sources.extractor.staging import list_staged, read_staging
    except ImportError as e:
        st.error(f"Could not import staging module: {e}")
        return

    staged_codes = list_staged()

    if not staged_codes:
        st.info(
            "No staged overlays found in `rules/staging/`. "
            "Run the extractor to generate overlays before using this tool."
        )
        return

    # ── Jurisdiction selector ─────────────────────────────────────────────────
    selected_code = st.selectbox(
        "Select staged jurisdiction overlay",
        options=staged_codes,
        help="Only jurisdictions with a file in rules/staging/ are shown.",
    )

    if not selected_code:
        return

    # ── Load overlay ──────────────────────────────────────────────────────────
    try:
        overlay = read_staging(selected_code)
    except Exception as e:
        st.error(f"Failed to load staged overlay for {selected_code}: {e}")
        return

    with st.expander(f"Staged overlay — {selected_code}", expanded=False):
        st.json(overlay.model_dump() if hasattr(overlay, "model_dump") else vars(overlay))

    st.divider()

    # ── Identify customers in this jurisdiction ───────────────────────────────
    customers_df = st.session_state.customers_df
    if "jurisdiction" not in customers_df.columns:
        st.error("customers DataFrame has no `jurisdiction` column — cannot filter.")
        return

    jur_customers = customers_df[
        customers_df["jurisdiction"].astype(str).str.upper() == selected_code.upper()
    ]

    if jur_customers.empty:
        st.warning(
            f"No customers found with jurisdiction = **{selected_code}**. "
            "Impact analysis requires at least one customer in this jurisdiction."
        )
        return

    st.markdown(
        f"**{len(jur_customers)}** customer(s) in jurisdiction **{selected_code}** "
        "will be evaluated."
    )

    # ── Run button ────────────────────────────────────────────────────────────
    if not st.button("Run Impact Analysis", type="primary"):
        return

    # ── Evaluate current decisions ────────────────────────────────────────────
    customer_ids = jur_customers["customer_id"].astype(str).tolist()

    progress = st.progress(0, text="Evaluating current decisions…")
    current_decisions = []
    errors = []

    for i, cid in enumerate(customer_ids):
        try:
            result = engine.evaluate_customer(cid)
            current_decisions.append(result)
        except Exception as exc:
            errors.append(f"{cid}: {exc}")
        progress.progress((i + 1) / len(customer_ids), text=f"Evaluated {i+1}/{len(customer_ids)}")

    progress.empty()

    if errors:
        with st.expander(f"⚠️ {len(errors)} evaluation error(s)", expanded=False):
            for e in errors:
                st.text(e)

    if not current_decisions:
        st.error("No decisions could be evaluated. Check the engine logs.")
        return

    # ── Run compute_impact ────────────────────────────────────────────────────
    try:
        from sources.impact.impact import compute_impact
    except ImportError as e:
        st.error(f"Could not import compute_impact: {e}")
        return

    try:
        report = compute_impact(selected_code, overlay, current_decisions)
    except Exception as e:
        st.error(f"compute_impact() failed: {e}")
        return

    # ── Log the analysis ──────────────────────────────────────────────────────
    summary = report.summary()
    log(
        "IMPACT_ANALYSIS_RUN",
        details={
            "jurisdiction": selected_code,
            "total_evaluated": summary.get("total_evaluated"),
            "flip_count": summary.get("flip_count"),
            "skipped": summary.get("skipped"),
        },
    )

    # ── Display summary ───────────────────────────────────────────────────────
    st.subheader("Impact Summary")
    c1, c2, c3 = st.columns(3)
    c1.metric("Customers evaluated", summary.get("total_evaluated", 0))
    c2.metric("Disposition flips", summary.get("flip_count", 0),
              delta=None if summary.get("flip_count", 0) == 0 else "⚠️ review before merging")
    c3.metric("Skipped (no jurisdiction match)", summary.get("skipped", 0))

    st.divider()

    # ── Flip table ────────────────────────────────────────────────────────────
    if not report.flips:
        st.success(
            f"No disposition flips detected. Merging **{selected_code}** overlay "
            "would not change any current decisions."
        )
        return

    st.warning(
        f"**{summary['flip_count']}** decision(s) would change disposition "
        f"if the **{selected_code}** overlay is merged."
    )

    flip_rows = [
        {
            "Customer ID": f.customer_id,
            "Jurisdiction": f.jurisdiction,
            "Current Disposition": f.from_disposition,
            "New Disposition": f.to_disposition,
        }
        for f in report.flips
    ]
    flip_df = pd.DataFrame(flip_rows)

    # Highlight direction of change
    def _colour_disposition(val):
        colours = {
            "REJECT": "background-color: #fde8e8; color: #c0392b",
            "REVIEW": "background-color: #fef9e7; color: #b7770d",
            "PASS_WITH_NOTES": "background-color: #eaf4fb; color: #1a6fa0",
            "PASS": "background-color: #eafaf1; color: #1e8449",
        }
        return colours.get(str(val).upper(), "")

    st.dataframe(
        flip_df.style.applymap(
            _colour_disposition,
            subset=["Current Disposition", "New Disposition"],
        ),
        use_container_width=True,
    )

    st.caption(
        "These flips are **hypothetical** — no data has been changed. "
        "Use `merge_staged_overlay()` with a named reviewer to apply the overlay."
    )
