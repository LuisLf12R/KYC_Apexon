"""Utilities to harden pandas DataFrames before Streamlit/Arrow conversion."""

from __future__ import annotations

import json
from typing import Any, Iterable, Optional

import pandas as pd

from src.canonical_schemas import CANONICAL_SCHEMAS

_DATASET_ALIAS = {
    "beneficial_ownership": "ubo",
}


def _normalize_dataset_type(dataset_type: Optional[str]) -> Optional[str]:
    if not dataset_type:
        return None
    return _DATASET_ALIAS.get(dataset_type, dataset_type)


def _to_text(value: Any) -> Any:
    """Convert mixed Python values to Arrow-safe textual values."""
    if pd.isna(value):
        return pd.NA
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, default=str, sort_keys=True)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    text = str(value).strip()
    return text if text else pd.NA


def coerce_expected_text_columns(
    df: pd.DataFrame,
    dataset_type: Optional[str] = None,
    additional_columns: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """
    Cast expected text/categorical columns to pandas StringDtype.

    This prevents booleans from leaking into textual fields that are later
    upper-cased or sent through Arrow conversion.
    """
    if df is None or df.empty:
        return df

    normalized = _normalize_dataset_type(dataset_type)
    text_columns = set(additional_columns or [])

    if normalized in CANONICAL_SCHEMAS:
        schema = CANONICAL_SCHEMAS[normalized]
        text_columns.update(schema.all_fields)
        text_columns.difference_update(schema.date_fields)
        for numeric_hint in ("txn_count", "total_volume", "ownership_percentage"):
            text_columns.discard(numeric_hint)

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].map(_to_text).astype("string")

    return df


def make_arrow_compatible(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize object columns so pyarrow sees a stable type per column."""
    if df is None or df.empty:
        return df

    safe_df = df.copy()
    for col in safe_df.columns:
        series = safe_df[col]
        if not pd.api.types.is_object_dtype(series):
            continue

        non_null = series.dropna()
        if non_null.empty:
            continue

        type_names = {type(v).__name__ for v in non_null}
        has_bool = any(isinstance(v, bool) for v in non_null)
        mixed_python_types = len(type_names) > 1
        non_scalar_values = any(isinstance(v, (dict, list, tuple, set, bytes)) for v in non_null)
        has_empty_string = any(isinstance(v, str) and not v.strip() for v in non_null)

        if has_bool or mixed_python_types or non_scalar_values or has_empty_string:
            safe_df[col] = series.map(_to_text).astype("string")

    return safe_df
