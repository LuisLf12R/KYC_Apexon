"""Read/write helpers for rules/staging/."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from rules.schema import JurisdictionOverlay

_STAGING_DIR = Path(__file__).parent.parent.parent / "rules" / "staging"


def _staging_path(jurisdiction_code: str) -> Path:
    return _STAGING_DIR / f"{jurisdiction_code}.json"


def write_staging(overlay: JurisdictionOverlay) -> Path:
    """Serialise a validated JurisdictionOverlay to rules/staging/<CODE>.json.

    Creates the staging directory if absent.
    Returns the path written.
    """
    _STAGING_DIR.mkdir(parents=True, exist_ok=True)
    path = _staging_path(overlay.jurisdiction_code)
    path.write_text(
        json.dumps(overlay.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return path


def read_staging(jurisdiction_code: str) -> JurisdictionOverlay:
    """Load and validate a staged overlay. Raises FileNotFoundError if absent."""
    path = _staging_path(jurisdiction_code)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return JurisdictionOverlay.model_validate(raw)


def list_staged() -> List[str]:
    """Return jurisdiction codes that have staged overlays (alphabetically sorted)."""
    if not _STAGING_DIR.exists():
        return []
    return sorted(
        p.stem for p in _STAGING_DIR.glob("*.json")
    )
