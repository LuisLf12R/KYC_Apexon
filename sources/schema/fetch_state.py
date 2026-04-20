"""
Pydantic v2 schema for sources/fetch_state.yaml.

Structure
---------
fetch_state.yaml
  schema_version: "1.0"
  generated_at: <ISO datetime string>
  states:
    <source_id>:           # e.g. "FATF-REC"
      <url_label>:         # e.g. "landing"
        last_fetched_at: null | ISO datetime string
        last_hash: null | hex string
        last_status: null | "ok" | "changed" | "error"
        last_changed_at: null | ISO datetime string
        error_message: null | string

Models
------
FetchStatus  — enum: ok | changed | error
UrlState     — state for one (source_id, url_label) pair
FetchStateManifest — top-level wrapper

load_fetch_state(path)  — loads and validates fetch_state.yaml
save_fetch_state(manifest, path) — writes manifest to fetch_state.yaml
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from typing import Dict, Optional

import yaml
from pydantic import BaseModel


class FetchStatus(str, Enum):
    ok = "ok"
    changed = "changed"
    error = "error"


class UrlState(BaseModel):
    last_fetched_at: Optional[str] = None   # ISO datetime string or null
    last_hash: Optional[str] = None          # hex digest or null
    last_status: Optional[FetchStatus] = None
    last_changed_at: Optional[str] = None   # ISO datetime string or null
    error_message: Optional[str] = None

    class Config:
        use_enum_values = True


class FetchStateManifest(BaseModel):
    schema_version: str
    generated_at: str                                     # ISO datetime string
    states: Dict[str, Dict[str, UrlState]] = {}
    # states[source_id][url_label] = UrlState

    class Config:
        use_enum_values = True


def load_fetch_state(
    path: str | os.PathLike | None = None,
) -> FetchStateManifest:
    """Load and validate fetch_state.yaml. Returns empty manifest if file absent."""
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "..", "fetch_state.yaml")
    if not os.path.exists(path):
        return FetchStateManifest(
            schema_version="1.0",
            generated_at=datetime.utcnow().isoformat(),
            states={},
        )
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return FetchStateManifest.model_validate(raw)


def save_fetch_state(
    manifest: FetchStateManifest,
    path: str | os.PathLike | None = None,
) -> None:
    """Write FetchStateManifest to fetch_state.yaml."""
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "..", "fetch_state.yaml")
    data = manifest.model_dump()
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
