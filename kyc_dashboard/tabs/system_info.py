TAB_CODE = '    touch()\n    st.markdown("### System Information")\n    c1, c2 = st.columns(2)\n    with c1:\n        st.markdown("**Datasets**")\n        if st.session_state.engines_initialized:\n            eng = st.session_state.kyc_engine\n            st.metric("Customers", len(st.session_state.customers_df))\n            st.metric("Screenings",\n                      len(eng.screenings) if eng.screenings is not None else 0)\n            st.metric("ID Verifications",\n                      len(eng.id_verifications) if eng.id_verifications is not None else 0)\n            st.metric("Transactions",\n                      len(eng.transactions) if eng.transactions is not None else 0)\n        else:\n            st.info("No datasets loaded.")\n    with c2:\n        st.markdown("**Active Prompts**")\n        if PROMPTS:\n            for pid, p in PROMPTS.items():\n                st.markdown(f"- `{pid}` v{p.get(\'version\', \'?\')} "\n                            f"({p.get(\'created_at\', \'\')[:10]})")\n        else:\n            st.warning("No prompts loaded. Commit the prompts/ folder to GitHub.")\n    st.divider()\n    st.markdown(f"""\n    **Hosting:** Railway | **Framework:** Streamlit | **Ruleset:** `{RULESET_VERSION}`  \n    **Timeout:** {INACTIVITY_TIMEOUT_SEC // 60} min (FFIEC / PSD2) | **Warning at:** {INACTIVITY_WARNING_SEC // 60} min  \n    PII clears from memory on session end. Audit trail stores metadata only.\n    """)\n\n# ════════════════════════════════════════════════════════\n# TAB 6: APPROVAL QUEUE\n# ════════════════════════════════════════════════════════\n'


def render(user, role, logger):
    import kyc_dashboard.main as a

    ns = dict(a.__dict__)
    ns.update({'user': user, 'role': role, 'logger': logger})
    exec(TAB_CODE, ns, ns)
