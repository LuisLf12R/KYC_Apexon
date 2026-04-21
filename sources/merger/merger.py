"""
sources/merger/merger.py

Staged-overlay → live-ruleset merge tooling.

Hard constraints (architectural decisions §3, §6, §10):
- Merger NEVER writes to kyc_rules_v2.0.json without a named, non-null reviewer.
- _dry_run=True validates and returns MergeResult without touching disk.
- Merger loads raw JSON dicts, mutates in place, validates the full
  RulesetManifest round-trip, then writes back — no partial writes.
- Merger is the ONLY code path that writes to kyc_rules_v2.0.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from rules.schema.dimensions import JurisdictionOverlay
from rules.schema.ruleset import ChangelogEntry, RulesetManifest

# ── Paths (overridable in tests via arguments) ─────────────────────────────────

_LIVE_RULESET = Path("rules/kyc_rules_v2.0.json")
_STAGING_DIR = Path("rules/staging")


# ── Public exception ───────────────────────────────────────────────────────────

class MergeError(Exception):
    """Raised when a merge precondition fails (no reviewer, schema invalid, etc.)."""


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class MergeResult:
    jurisdiction_code: str
    status: str                          # "merged" | "dry_run" | "error"
    is_new: bool                         # True if jurisdiction was not previously in live ruleset
    changelog_version: str
    reviewed_by: str
    error: Optional[str] = None


# ── Reviewer validation ────────────────────────────────────────────────────────

def validate_reviewer(reviewed_by: Optional[str]) -> str:
    """
    Enforce that reviewed_by is a non-empty, non-null string.
    Raises MergeError if the gate fails.
    This is the §6 hard constraint: no merge without named reviewer sign-off.
    """
    if not reviewed_by or not reviewed_by.strip():
        raise MergeError(
            "reviewed_by must be a non-empty string. "
            "No ruleset merge is permitted without a named reviewer (§6)."
        )
    return reviewed_by.strip()


# ── Staging loader ─────────────────────────────────────────────────────────────

def load_staged_overlay(
    jurisdiction_code: str,
    staging_dir: Path = _STAGING_DIR,
) -> JurisdictionOverlay:
    """
    Read rules/staging/<CODE>.json and validate as JurisdictionOverlay.
    Raises MergeError if file is missing or schema-invalid.
    """
    path = staging_dir / f"{jurisdiction_code}.json"
    if not path.exists():
        raise MergeError(
            f"No staged overlay found for {jurisdiction_code!r} at {path}. "
            "Run the extractor first or confirm the jurisdiction code."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return JurisdictionOverlay.model_validate(data)
    except Exception as exc:
        raise MergeError(
            f"Staged overlay for {jurisdiction_code!r} failed schema validation: {exc}"
        ) from exc


# ── Live ruleset I/O ───────────────────────────────────────────────────────────

def load_live_ruleset_dict(ruleset_path: Path = _LIVE_RULESET) -> Dict[str, Any]:
    """Load kyc_rules_v2.0.json as a raw dict (preserves all fields including reviewed_by)."""
    if not ruleset_path.exists():
        raise MergeError(f"Live ruleset not found at {ruleset_path}")
    return json.loads(ruleset_path.read_text(encoding="utf-8"))


def validate_live_dict(raw: Dict[str, Any]) -> RulesetManifest:
    """Full Pydantic round-trip validation. Raises MergeError on failure."""
    try:
        return RulesetManifest.model_validate(raw)
    except Exception as exc:
        raise MergeError(f"Live ruleset failed schema validation after mutation: {exc}") from exc


# ── Changelog builder ──────────────────────────────────────────────────────────

def build_changelog_entry(
    jurisdiction_code: str,
    is_new: bool,
    reviewed_by: str,
    pr_url: Optional[str] = None,
    ruleset_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a changelog entry dict for a jurisdiction merge.
    reviewed_by is always non-null here (validate_reviewer has already been called).
    """
    action = "add" if is_new else "update"
    change_msg = f"{action} {jurisdiction_code} jurisdiction overlay"
    if pr_url:
        change_msg += f" — {pr_url}"

    return {
        "version": ruleset_version or "auto",
        "date": date.today().isoformat(),
        "change": change_msg,
        "author": "merger",
        "reviewed_by": reviewed_by,
    }


# ── Core merge operation ───────────────────────────────────────────────────────

def apply_overlay_to_dict(
    raw: Dict[str, Any],
    overlay: JurisdictionOverlay,
    reviewed_by: str,
    pr_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Upsert the overlay into raw["jurisdictions"], append a changelog entry.
    Returns a mutated copy; does NOT write to disk.
    """
    import copy
    raw = copy.deepcopy(raw)

    code = overlay.jurisdiction_code
    is_new = code not in raw.get("jurisdictions", {})

    # Upsert jurisdiction
    if "jurisdictions" not in raw:
        raw["jurisdictions"] = {}
    raw["jurisdictions"][code] = overlay.model_dump(mode="json")

    # Append changelog entry
    entry = build_changelog_entry(
        jurisdiction_code=code,
        is_new=is_new,
        reviewed_by=reviewed_by,
        pr_url=pr_url,
        ruleset_version=raw.get("version"),
    )
    raw.setdefault("changelog", []).append(entry)

    return raw, is_new


# ── Public API ─────────────────────────────────────────────────────────────────

def merge_staged_overlay(
    jurisdiction_code: str,
    reviewed_by: str,
    pr_url: Optional[str] = None,
    *,
    _dry_run: bool = False,
    _staging_dir: Path = _STAGING_DIR,
    _ruleset_path: Path = _LIVE_RULESET,
) -> MergeResult:
    """
    Merge a single staged overlay into the live ruleset.

    Parameters
    ----------
    jurisdiction_code : str
        ISO-like code matching the staging filename, e.g. "CAN".
    reviewed_by : str
        Named reviewer — mandatory, non-null (§6 gate).
    pr_url : str, optional
        PR URL recorded in changelog for traceability.
    _dry_run : bool
        If True, validate everything but do not write to disk.
    _staging_dir, _ruleset_path :
        Override paths for testing.

    Returns
    -------
    MergeResult
    """
    # Gate 1 — reviewer
    reviewer = validate_reviewer(reviewed_by)

    # Gate 2 — load and validate staged overlay
    overlay = load_staged_overlay(jurisdiction_code, staging_dir=_staging_dir)

    # Gate 3 — load live ruleset
    raw = load_live_ruleset_dict(_ruleset_path)

    # Gate 4 — apply and validate full round-trip
    mutated, is_new = apply_overlay_to_dict(raw, overlay, reviewer, pr_url)
    validate_live_dict(mutated)   # raises MergeError if schema breaks

    if not _dry_run:
        _ruleset_path.write_text(
            json.dumps(mutated, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return MergeResult(
        jurisdiction_code=jurisdiction_code,
        status="dry_run" if _dry_run else "merged",
        is_new=is_new,
        changelog_version=mutated.get("version", "unknown"),
        reviewed_by=reviewer,
    )


def merge_all_staged(
    reviewed_by: str,
    pr_url: Optional[str] = None,
    *,
    _dry_run: bool = False,
    _staging_dir: Path = _STAGING_DIR,
    _ruleset_path: Path = _LIVE_RULESET,
) -> List[MergeResult]:
    """
    Merge all staged overlays found in staging_dir.
    Skips PR_DRAFT.md and any non-.json files.
    Logs and records errors per jurisdiction — does not abort on first failure.
    """
    reviewer = validate_reviewer(reviewed_by)

    staged_files = sorted(_staging_dir.glob("*.json")) if _staging_dir.exists() else []
    if not staged_files:
        return []

    results: List[MergeResult] = []
    for staged_path in staged_files:
        code = staged_path.stem
        try:
            result = merge_staged_overlay(
                code,
                reviewer,
                pr_url=pr_url,
                _dry_run=_dry_run,
                _staging_dir=_staging_dir,
                _ruleset_path=_ruleset_path,
            )
            results.append(result)
        except MergeError as exc:
            results.append(
                MergeResult(
                    jurisdiction_code=code,
                    status="error",
                    is_new=False,
                    changelog_version="unknown",
                    reviewed_by=reviewer,
                    error=str(exc),
                )
            )
    return results
