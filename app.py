from dotenv import load_dotenv
load_dotenv()

# Start the banker sidecar at process boot — before any Streamlit session exists.
# Running here (module level, outside st.cache_resource) means the subprocess
# is fully independent of Streamlit's session lifecycle and hot-reload cycles.
import socket as _sock, time as _time
try:
    from kyc_dashboard.sidecar import start_sidecar_thread
    start_sidecar_thread()
    # Wait up to 5 s so the port is bound before the first request arrives.
    for _ in range(50):
        try:
            _c = _sock.create_connection(("127.0.0.1", 8502), timeout=0.1)
            _c.close()
            break
        except OSError:
            _time.sleep(0.1)
except Exception:
    pass

import streamlit as st
from kyc_dashboard.styles import inject_styles
from kyc_dashboard.state import init_state
from kyc_dashboard.main import render_login, render_main
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
