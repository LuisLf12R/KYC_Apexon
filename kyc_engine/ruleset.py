"""
kyc_engine/ruleset.py
Single source of truth for loading and caching the active RulesetManifest.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from rules.schema.ruleset import RulesetManifest

_RULESET_DIR = Path(__file__).parent.parent / "rules"
_DEFAULT_FILENAME = "kyc_rules_v1.1.json"

_active_manifest: Optional[RulesetManifest] = None


def load_ruleset(filename: str = _DEFAULT_FILENAME) -> RulesetManifest:
    """
    Load, validate, and cache the active ruleset manifest.
    Returns a RulesetManifest (Pydantic model), not a raw dict.
    Subsequent calls with the same filename return the cached instance.
    """
    global _active_manifest
    if _active_manifest is not None:
        return _active_manifest

    path = _RULESET_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Ruleset file not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    _active_manifest = RulesetManifest.model_validate(raw)
    return _active_manifest


def get_active_ruleset_version() -> str:
    """Single accessor for the active ruleset version string."""
    return load_ruleset().version


def reset_ruleset_cache() -> None:
    """For use in tests only — clears the cached manifest."""
    global _active_manifest
    _active_manifest = None
