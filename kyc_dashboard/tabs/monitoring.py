"""Source monitoring tab for change detection and re-evaluation targeting."""

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from sources.monitoring import MonitoringService


def render(user, role, logger):
    st.header("Source Monitoring")
    st.caption(
        "Check for regulatory source changes since the last snapshot and identify "
        "which customers should be re-evaluated."
    )

    if not st.session_state.get("engines_initialized"):
        st.warning("Engine must be loaded first.")
        return

    if "monitoring_snapshot" not in st.session_state:
        st.session_state.monitoring_snapshot = None
    if "monitoring_report" not in st.session_state:
        st.session_state.monitoring_report = None

    svc = MonitoringService()
    customers_df = st.session_state.get("customers_df")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Take Snapshot", type="secondary", use_container_width=True):
            snap = svc.snapshot()
            st.session_state.monitoring_snapshot = snap
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            st.success(f"Snapshot captured at {ts}")

    with c2:
        run_disabled = st.session_state.monitoring_snapshot is None
        if st.button(
            "Run Check",
            type="primary",
            use_container_width=True,
            disabled=run_disabled,
        ):
            report = svc.check(st.session_state.monitoring_snapshot, customers_df)
            st.session_state.monitoring_report = report
            st.success("Monitoring check complete.")

    if st.session_state.monitoring_snapshot is None:
        st.info("No previous snapshot yet. Click **Take Snapshot** to initialize baseline.")

    report = st.session_state.monitoring_report
    if report is None:
        return

    st.divider()
    st.subheader("Monitoring Results")

    m1, m2, m3 = st.columns(3)
    m1.metric("Changed sources", len(report.changed_sources))
    m2.metric("Affected jurisdictions", len(report.affected_jurisdictions))
    m3.metric("Customers to review", len(report.customer_ids_to_review))

    st.markdown("#### Changed Sources")
    if report.changed_sources:
        rows = [
            {
                "source_id": sc.source_id,
                "change_type": sc.change_type,
                "jurisdiction": sc.jurisdiction,
                "previous_hash": sc.previous_hash,
                "current_hash": sc.current_hash,
            }
            for sc in report.changed_sources
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No changed sources detected.")

    st.markdown("#### Affected Jurisdictions")
    if report.affected_jurisdictions:
        st.write(sorted(report.affected_jurisdictions))
    else:
        st.write(["None"])

    st.markdown("#### Customers to Review")
    if report.customer_ids_to_review:
        st.dataframe(
            pd.DataFrame({"customer_id": report.customer_ids_to_review}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No customers flagged for re-evaluation.")

    with st.expander("Skipped Sources", expanded=False):
        if report.skipped_sources:
            st.write(report.skipped_sources)
        else:
            st.write(["None"])
