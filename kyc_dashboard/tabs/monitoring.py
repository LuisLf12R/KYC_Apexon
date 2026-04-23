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

    # ── UBO Change Detection ───────────────────────────────────────────────
    st.divider()
    st.subheader("UBO Change Detection")
    st.caption(
        "Compare current beneficial-ownership records against a snapshot "
        "to identify customers whose UBO structure has changed."
    )

    from sources.monitoring.ubo_monitoring import UBOMonitoringService

    if "ubo_snapshot" not in st.session_state:
        st.session_state.ubo_snapshot = None
    if "ubo_report" not in st.session_state:
        st.session_state.ubo_report = None

    ubo_df = st.session_state.get("beneficial_owners_df")
    if ubo_df is None:
        engine = st.session_state.get("engine")
        if engine is not None and hasattr(engine, "beneficial_owners"):
            ubo_df = engine.beneficial_owners

    ubo_svc = UBOMonitoringService()

    uc1, uc2 = st.columns(2)
    with uc1:
        if st.button("Take UBO Snapshot", type="secondary", use_container_width=True):
            if ubo_df is not None and not ubo_df.empty:
                st.session_state.ubo_snapshot = ubo_svc.snapshot(ubo_df)
                st.success("UBO snapshot captured.")
            else:
                st.warning("No UBO data available to snapshot.")

    with uc2:
        ubo_run_disabled = st.session_state.ubo_snapshot is None
        if st.button(
            "Run UBO Check",
            type="primary",
            use_container_width=True,
            disabled=ubo_run_disabled,
        ):
            ubo_report = ubo_svc.check(st.session_state.ubo_snapshot, ubo_df)
            st.session_state.ubo_report = ubo_report
            st.success("UBO monitoring check complete.")

    if st.session_state.ubo_snapshot is None:
        st.info("No UBO snapshot yet. Click **Take UBO Snapshot** to initialize.")

    ubo_report = st.session_state.ubo_report
    if ubo_report is not None:
        um1, um2 = st.columns(2)
        um1.metric("UBO Changes", ubo_report.change_count)
        um2.metric("Affected Customers", ubo_report.customer_count)

        if ubo_report.changes:
            ubo_rows = [
                {
                    "customer_id": c.customer_id,
                    "owner_name": c.owner_name,
                    "change_type": c.change_type,
                    "previous": c.previous_value or "",
                    "current": c.current_value or "",
                }
                for c in ubo_report.changes
            ]
            st.dataframe(
                pd.DataFrame(ubo_rows), use_container_width=True, hide_index=True
            )
        else:
            st.info("No UBO changes detected.")
