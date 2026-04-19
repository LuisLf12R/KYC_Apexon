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
_DEFAULT_FILENAME = "kyc_rules_v2.0.json"

_active_manifest: Optional[RulesetManifest] = None
_ruleset_cache: Optional[RulesetManifest] = None


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


def get_jurisdiction_params(jurisdiction_code: str) -> dict:
    """
    Return merged dimension parameters for a given jurisdiction.

    Merge strategy: baseline dimension_parameters fields are used as
    the base. Any fields present in the jurisdiction's dimension_overrides
    are merged in at the sub-field level (not whole-object replace).

    Example:
        baseline beneficial_ownership = {ownership_threshold_pct: 25.0, max_chain_depth: 4}
        SGP override = {velocity_window_days: 30}  # different dimension — unrelated
        HKG override beneficial_ownership = {ownership_threshold_pct: 10.0}
        → merged HKG beneficial_ownership = {ownership_threshold_pct: 10.0, max_chain_depth: 4}

    Falls back to baseline for any jurisdiction_code not present in the
    manifest, so existing tests and customers without a jurisdiction match
    continue to work unchanged.

    Args:
        jurisdiction_code: ISO 3166-1 alpha-3 or regional code string,
                           e.g. "USA", "GBR", "EU", "SGP", "HKG".
                           Matched case-sensitively against manifest keys.

    Returns:
        dict with same structure as manifest.dimension_parameters,
        with jurisdiction overrides applied where present.
    """
    manifest = load_ruleset()

    # Build baseline as a plain dict (model_dump for Pydantic v2)
    try:
        baseline = manifest.dimension_parameters.model_dump()
    except AttributeError:
        baseline = manifest.dimension_parameters.dict()

    # No jurisdictions block or code not found → return baseline unchanged
    if not manifest.jurisdictions or jurisdiction_code not in manifest.jurisdictions:
        return baseline

    overlay = manifest.jurisdictions[jurisdiction_code]
    overrides = overlay.dimension_overrides  # Dict[str, Any]

    if not overrides:
        return baseline

    # Deep merge: for each dimension key in overrides, merge sub-fields
    # into the corresponding baseline dict rather than replacing it wholesale.
    import copy
    merged = copy.deepcopy(baseline)

    for dimension_key, override_fields in overrides.items():
        if dimension_key not in merged:
            # New dimension key not in baseline — add it directly
            merged[dimension_key] = override_fields
        elif isinstance(merged[dimension_key], dict) and isinstance(override_fields, dict):
            # Sub-field level merge: baseline fields not in override are preserved
            merged[dimension_key] = {**merged[dimension_key], **override_fields}
        else:
            # Scalar override — replace directly
            merged[dimension_key] = override_fields

    return merged


def get_jurisdiction_rules(jurisdiction_code: str) -> dict:
    """
    Return the combined hard-reject and review rules for a jurisdiction.

    Combines baseline rules with any additional_hard_reject_rules and
    additional_review_rules defined in the jurisdiction overlay.

    Falls back to baseline rules if jurisdiction_code is not in manifest.

    Args:
        jurisdiction_code: ISO 3166-1 alpha-3 or regional code string.

    Returns:
        dict with keys:
            "hard_reject_rules": list of HardRejectRule-compatible dicts
            "review_rules":      list of ReviewRule-compatible dicts
    """
    manifest = load_ruleset()

    try:
        hard_reject = [r.model_dump() for r in manifest.hard_reject_rules]
        review = [r.model_dump() for r in manifest.review_rules]
    except AttributeError:
        hard_reject = [r.dict() for r in manifest.hard_reject_rules]
        review = [r.dict() for r in manifest.review_rules]

    if not manifest.jurisdictions or jurisdiction_code not in manifest.jurisdictions:
        return {"hard_reject_rules": hard_reject, "review_rules": review}

    overlay = manifest.jurisdictions[jurisdiction_code]

    additional_hr = overlay.additional_hard_reject_rules or []
    additional_rv = overlay.additional_review_rules or []

    return {
        "hard_reject_rules": hard_reject + additional_hr,
        "review_rules": review + additional_rv,
    }


def reset_ruleset_cache() -> None:
    """For use in tests only — clears the cached manifest."""
    global _active_manifest
    _active_manifest = None
