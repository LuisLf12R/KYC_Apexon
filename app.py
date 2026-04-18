from dotenv import load_dotenv
import streamlit as st
from kyc_dashboard.styles import inject_styles
from kyc_dashboard.state import init_state
from kyc_dashboard.main import render_login, render_main

load_dotenv()
st.set_page_config(page_title="KYC Compliance Platform", page_icon="🏦", layout="wide", initial_sidebar_state="collapsed")
inject_styles()
init_state()

if not st.session_state.authenticated:
    render_login()
else:
    from kyc_dashboard.state import check_timeout
    if not check_timeout():
        render_login()
    else:
        render_main()
