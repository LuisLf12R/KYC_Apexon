"""
sources/release/release.py

Semver release tooling for the KYC ruleset.

Version format:  "kyc-rules-v<major>.<minor>[.<patch>]"
  Examples:       kyc-rules-v2.1   kyc-rules-v2.1.1   kyc-rules-v3.0

Hard constraints:
- No release without a named reviewer on the most-recent changelog entry (§6).
- _dry_run=True validates and returns ReleaseResult without writing to disk.
- create_release() is the ONLY code path that bumps version + writes the file.
- Merger writes jurisdiction overlays; release tooling bumps the manifest version.
  They are separate operations — a release may include 0-N merged overlays.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rules.schema.ruleset import RulesetManifest

# ── Default path ───────────────────────────────────────────────────────────────

_LIVE_RULESET = Path("rules/kyc_rules_v2.0.json")

# ── Version prefix expected in all ruleset version strings ────────────────────

_VERSION_PREFIX = "kyc-rules-v"
_VERSION_RE = re.compile(
    r"^(kyc-rules-v)(\d+)\.(\d+)(?:\.(\d+))?$"
)


# ── Public exception ───────────────────────────────────────────────────────────

class ReleaseError(Exception):
    """Raised when a release precondition fails."""


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class ReleaseResult:
    previous_version: str
    new_version: str
    bump_type: str          # "major" | "minor" | "patch"
    reviewed_by: str
    status: str             # "released" | "dry_run"
    changelog_entry: Dict[str, Any]


# ── Version parsing and bumping ────────────────────────────────────────────────

def parse_version(version_str: str) -> Tuple[str, List[int]]:
    """
    Parse a ruleset version string into (prefix, parts).

    "kyc-rules-v2.1"   → ("kyc-rules-v", [2, 1])
    "kyc-rules-v2.1.3" → ("kyc-rules-v", [2, 1, 3])

    Raises ReleaseError for unrecognised formats.
    """
    m = _VERSION_RE.match(version_str.strip())
    if not m:
        raise ReleaseError(
            f"Cannot parse version string {version_str!r}. "
            f"Expected format: '{_VERSION_PREFIX}<major>.<minor>[.<patch>]'"
        )
    prefix = m.group(1)
    major = int(m.group(2))
    minor = int(m.group(3))
    patch = int(m.group(4)) if m.group(4) is not None else None
    parts = [major, minor] if patch is None else [major, minor, patch]
    return prefix, parts


def bump_version(version_str: str, bump_type: str) -> str:
    """
    Increment a ruleset version string.

    bump_type:
        "major" — increment major, reset minor (and patch if present) to 0
        "minor" — increment minor, reset patch to 0 if present
        "patch" — increment patch; if no patch component, append .1

    Returns the new version string with the same prefix.
    Raises ReleaseError for unknown bump_type.
    """
    if bump_type not in ("major", "minor", "patch"):
        raise ReleaseError(
            f"Unknown bump_type {bump_type!r}. Must be 'major', 'minor', or 'patch'."
        )

    prefix, parts = parse_version(version_str)
    has_patch = len(parts) == 3

    if bump_type == "major":
        parts = [parts[0] + 1, 0] + ([0] if has_patch else [])
    elif bump_type == "minor":
        parts = [parts[0], parts[1] + 1] + ([0] if has_patch else [])
    else:  # patch
        if has_patch:
            parts = [parts[0], parts[1], parts[2] + 1]
        else:
            parts = [parts[0], parts[1], 1]

    return prefix + ".".join(str(p) for p in parts)


# ── Precondition gate ──────────────────────────────────────────────────────────

def validate_release_preconditions(raw: Dict[str, Any]) -> None:
    """
    Check that the most-recent changelog entry has a non-null reviewed_by.

    This enforces §6: no release can be tagged from a ruleset whose last
    change has not been signed off by a named reviewer.

    Raises ReleaseError if the gate fails.
    """
    changelog = raw.get("changelog", [])
    if not changelog:
        raise ReleaseError(
            "Ruleset changelog is empty. At least one reviewed entry is required "
            "before cutting a release."
        )
    latest = changelog[-1]
    reviewed_by = latest.get("reviewed_by")
    if not reviewed_by or not str(reviewed_by).strip():
        raise ReleaseError(
            f"Most-recent changelog entry (version={latest.get('version')!r}) "
            "has reviewed_by=null. A release cannot be tagged until the last "
            "change has a named reviewer sign-off (§6)."
        )


# ── Changelog entry builder ────────────────────────────────────────────────────

def build_release_entry(
    new_version: str,
    bump_type: str,
    reviewed_by: str,
    author: str,
    change_summary: str,
) -> Dict[str, Any]:
    return {
        "version": new_version,
        "date": date.today().isoformat(),
        "change": f"{bump_type} release: {change_summary}",
        "author": author,
        "reviewed_by": reviewed_by,
    }


# ── Orchestrator ───────────────────────────────────────────────────────────────

def create_release(
    bump_type: str,
    reviewed_by: str,
    *,
    author: str = "release-pipeline",
    change_summary: str = "scheduled release",
    _dry_run: bool = False,
    _ruleset_path: Path = _LIVE_RULESET,
) -> ReleaseResult:
    """
    Cut a new ruleset release.

    Steps:
    1. Validate reviewed_by non-empty.
    2. Load live ruleset dict.
    3. validate_release_preconditions — latest changelog entry must have reviewer.
    4. Bump version string.
    5. Build release changelog entry.
    6. Mutate raw dict: update version, append entry.
    7. Full RulesetManifest round-trip validation.
    8. Write to disk (skipped if _dry_run=True).

    Parameters
    ----------
    bump_type : "major" | "minor" | "patch"
    reviewed_by : named reviewer — mandatory
    author : recorded in changelog entry (default: "release-pipeline")
    change_summary : human-readable description of what changed
    _dry_run : if True, validate but do not write
    _ruleset_path : override for testing
    """
    import copy

    # Gate 1 — reviewer
    if not reviewed_by or not reviewed_by.strip():
        raise ReleaseError(
            "reviewed_by must be a non-empty string. "
            "No release is permitted without a named reviewer (§6)."
        )
    reviewed_by = reviewed_by.strip()

    # Gate 2 — load
    if not _ruleset_path.exists():
        raise ReleaseError(f"Ruleset not found at {_ruleset_path}")
    raw = json.loads(_ruleset_path.read_text(encoding="utf-8"))

    # Gate 3 — preconditions
    validate_release_preconditions(raw)

    # Step 4 — bump
    previous_version = raw["version"]
    new_version = bump_version(previous_version, bump_type)

    # Step 5-6 — build entry, mutate
    raw = copy.deepcopy(raw)
    entry = build_release_entry(new_version, bump_type, reviewed_by, author, change_summary)
    raw["version"] = new_version
    raw["changelog"].append(entry)

    # Step 7 — full schema validation
    try:
        RulesetManifest.model_validate(raw)
    except Exception as exc:
        raise ReleaseError(
            f"Ruleset failed schema validation after version bump: {exc}"
        ) from exc

    # Step 8 — write
    if not _dry_run:
        _ruleset_path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return ReleaseResult(
        previous_version=previous_version,
        new_version=new_version,
        bump_type=bump_type,
        reviewed_by=reviewed_by,
        status="dry_run" if _dry_run else "released",
        changelog_entry=entry,
    )
