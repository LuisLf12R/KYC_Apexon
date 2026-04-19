def inject_styles():
    import streamlit as st

    st.markdown("""
<style>
/* Tab list container */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    padding: 4px 0 0 0;
    border-bottom: 2px solid rgba(255,255,255,0.08);
}
/* Individual tab */
.stTabs [data-baseweb="tab"] {
    font-size: 15px;
    font-weight: 500;
    padding: 12px 24px;
    border-radius: 6px 6px 0 0;
    color: rgba(255,255,255,0.6);
    background: transparent;
    border: none;
    letter-spacing: 0.01em;
    transition: color 0.15s ease, background 0.15s ease;
}
/* Hover state */
.stTabs [data-baseweb="tab"]:hover {
    color: rgba(255,255,255,0.9);
    background: rgba(255,255,255,0.05);
}
/* Active tab */
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #ffffff;
    font-weight: 700;
    background: rgba(255,255,255,0.06);
}
/* Active tab underline indicator */
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #0072B2;
    height: 3px;
    border-radius: 2px 2px 0 0;
}
/* Tab panel content area */
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 24px;
}
</style>
""", unsafe_allow_html=True)
