import pandas as pd
import streamlit as st

from src.dataframe_arrow_compat import ensure_arrow_compatible
from .state import DISPOSITION_CONFIG, can_unmask


def disposition_badge(disposition: str) -> str:
    """Return an HTML badge for a disposition value."""
    cfg = DISPOSITION_CONFIG.get(disposition, {"label": disposition, "color": "#999999", "icon": "?"})
    return (
        f"<span style='background:{cfg['color']};color:white;padding:3px 10px;"
        f"border-radius:4px;font-weight:bold;font-size:13px'>"
        f"{cfg['icon']} {cfg['label']}</span>"
    )


def show_disposition(disposition: str):
    """Render the appropriate Streamlit status element for a disposition."""
    cfg = DISPOSITION_CONFIG.get(disposition, {"label": disposition, "color": "#999", "icon": "?"})
    label = f"{cfg['icon']} {cfg['label']}"
    if disposition == "REJECT":
        st.error(label)
    elif disposition == "REVIEW":
        st.warning(label)
    elif disposition == "PASS_WITH_NOTES":
        st.info(label)
    else:
        st.success(label)


def mask(value, field_type="default"):
    if not st.session_state.pii_masked or can_unmask():
        return str(value) if value is not None else "N/A"
    masks = {
        "ssn": "***-**-****", "dob": "**/**/****",
        "account": f"****{str(value)[-4:]}" if value and len(str(value)) >= 4 else "****",
        "name": f"{str(value)[0]}***" if value else "***",
        "address": "[MASKED]", "default": "[MASKED]",
    }
    return masks.get(field_type, masks["default"])


def _format_conf_pct(conf):
    if conf is None or pd.isna(conf):
        return ""
    return f"{int(round(float(conf) * 100))}%"


def st_dataframe_safe(data, **kwargs):
    """Render DataFrames through an Arrow-safe normalization layer."""
    if isinstance(data, pd.DataFrame):
        data = ensure_arrow_compatible(data)
    st.dataframe(data, **kwargs)
