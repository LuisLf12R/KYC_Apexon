"""
tests/test_release.py
Tests for sources/release/release.py — REL-001 through REL-009
All mutating tests use tmp_path copies — never touch the live ruleset.
"""

import json
from pathlib import Path

import pytest

from sources.release import (
    ReleaseError,
    ReleaseResult,
    bump_version,
    create_release,
    parse_version,
    validate_release_preconditions,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def live_ruleset_dict() -> dict:
    return json.loads(Path("rules/kyc_rules_v2.0.json").read_text(encoding="utf-8"))


@pytest.fixture()
def ruleset_path_with_reviewer(tmp_path, live_ruleset_dict) -> Path:
    """Live ruleset copy where the last changelog entry has reviewed_by set."""
    data = live_ruleset_dict
    # Ensure the most-recent changelog entry has a reviewer
    if data["changelog"]:
        data["changelog"][-1]["reviewed_by"] = "Test Reviewer"
    p = tmp_path / "kyc_rules.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


@pytest.fixture()
def ruleset_path_no_reviewer(tmp_path, live_ruleset_dict) -> Path:
    """Live ruleset copy where the last changelog entry has reviewed_by=null."""
    data = live_ruleset_dict
    if data["changelog"]:
        data["changelog"][-1]["reviewed_by"] = None
    p = tmp_path / "kyc_rules_no_reviewer.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


# ── REL-001: parse_version handles 2-part and 3-part versions ─────────────────

def test_REL_001_parse_version():
    prefix, parts = parse_version("kyc-rules-v2.1")
    assert prefix == "kyc-rules-v"
    assert parts == [2, 1]

    prefix, parts = parse_version("kyc-rules-v2.1.3")
    assert prefix == "kyc-rules-v"
    assert parts == [2, 1, 3]


def test_REL_001b_parse_version_invalid():
    with pytest.raises(ReleaseError, match="Cannot parse"):
        parse_version("v2.1")
    with pytest.raises(ReleaseError, match="Cannot parse"):
        parse_version("2.1.0")
    with pytest.raises(ReleaseError, match="Cannot parse"):
        parse_version("kyc-rules-v")


# ── REL-002: bump_version — all bump types on 2-part version ──────────────────

def test_REL_002_bump_major():
    assert bump_version("kyc-rules-v2.1", "major") == "kyc-rules-v3.0"


def test_REL_002b_bump_minor():
    assert bump_version("kyc-rules-v2.1", "minor") == "kyc-rules-v2.2"


def test_REL_002c_bump_patch_no_component():
    # Patch on 2-part version appends .1
    assert bump_version("kyc-rules-v2.1", "patch") == "kyc-rules-v2.1.1"


# ── REL-003: bump_version — all bump types on 3-part version ──────────────────

def test_REL_003_bump_patch_existing():
    assert bump_version("kyc-rules-v2.1.3", "patch") == "kyc-rules-v2.1.4"


def test_REL_003b_bump_minor_resets_patch():
    assert bump_version("kyc-rules-v2.1.3", "minor") == "kyc-rules-v2.2.0"


def test_REL_003c_bump_major_resets_all():
    assert bump_version("kyc-rules-v2.1.3", "major") == "kyc-rules-v3.0.0"


# ── REL-004: bump_version rejects unknown bump_type ───────────────────────────

def test_REL_004_unknown_bump_type():
    with pytest.raises(ReleaseError, match="Unknown bump_type"):
        bump_version("kyc-rules-v2.1", "hotfix")


# ── REL-005: validate_release_preconditions passes with reviewer ───────────────

def test_REL_005_preconditions_pass(live_ruleset_dict):
    # Inject a reviewer into the last entry
    live_ruleset_dict["changelog"][-1]["reviewed_by"] = "Alice"
    # Should not raise
    validate_release_preconditions(live_ruleset_dict)


# ── REL-006: validate_release_preconditions fails without reviewer ─────────────

def test_REL_006_preconditions_fail_no_reviewer(live_ruleset_dict):
    live_ruleset_dict["changelog"][-1]["reviewed_by"] = None
    with pytest.raises(ReleaseError, match="reviewed_by=null"):
        validate_release_preconditions(live_ruleset_dict)


def test_REL_006b_preconditions_fail_empty_changelog(live_ruleset_dict):
    live_ruleset_dict["changelog"] = []
    with pytest.raises(ReleaseError, match="changelog is empty"):
        validate_release_preconditions(live_ruleset_dict)


# ── REL-007: create_release dry_run does not write ────────────────────────────

def test_REL_007_dry_run_no_write(ruleset_path_with_reviewer):
    mtime_before = ruleset_path_with_reviewer.stat().st_mtime
    before = json.loads(ruleset_path_with_reviewer.read_text())
    expected_prev = before["version"]
    expected_new = bump_version(expected_prev, "minor")

    result = create_release(
        "minor",
        reviewed_by="Bob",
        change_summary="test release",
        _dry_run=True,
        _ruleset_path=ruleset_path_with_reviewer,
    )

    assert result.status == "dry_run"
    assert result.bump_type == "minor"
    assert result.reviewed_by == "Bob"
    assert result.previous_version == expected_prev
    assert result.new_version == expected_new
    # File untouched
    assert ruleset_path_with_reviewer.stat().st_mtime == mtime_before


# ── REL-008: create_release writes new version to disk ────────────────────────

def test_REL_008_real_release_writes(ruleset_path_with_reviewer):
    before = json.loads(ruleset_path_with_reviewer.read_text())
    expected_new = bump_version(before["version"], "patch")

    result = create_release(
        "patch",
        reviewed_by="Carol",
        change_summary="patch release test",
        _dry_run=False,
        _ruleset_path=ruleset_path_with_reviewer,
    )

    assert result.status == "released"
    assert result.new_version == expected_new

    updated = json.loads(ruleset_path_with_reviewer.read_text())
    assert updated["version"] == expected_new
    last_entry = updated["changelog"][-1]
    assert last_entry["reviewed_by"] == "Carol"
    assert last_entry["version"] == expected_new


# ── REL-009: create_release rejects blank reviewer ────────────────────────────

def test_REL_009_no_reviewer_rejected(ruleset_path_with_reviewer):
    with pytest.raises(ReleaseError, match="reviewed_by"):
        create_release(
            "minor",
            reviewed_by="",
            _dry_run=True,
            _ruleset_path=ruleset_path_with_reviewer,
        )
