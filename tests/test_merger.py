"""
tests/test_merger.py
Tests for sources/merger/merger.py — MRG-001 through MRG-010
All tests use _dry_run=True or temp file I/O — never touch the live ruleset.
"""

import json
import shutil
from pathlib import Path

import pytest

from sources.merger import MergeError, MergeResult, merge_all_staged, merge_staged_overlay
from sources.merger.merger import (
    apply_overlay_to_dict,
    build_changelog_entry,
    load_staged_overlay,
    validate_reviewer,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def live_ruleset_dict() -> dict:
    """Load the real kyc_rules_v2.0.json as a dict for mutation testing."""
    return json.loads(Path("rules/kyc_rules_v2.0.json").read_text(encoding="utf-8"))


@pytest.fixture()
def minimal_overlay_dict() -> dict:
    """Minimal valid JurisdictionOverlay dict for a fictional TEST jurisdiction."""
    return {
        "jurisdiction_code": "TST",
        "regulators": ["TEST-REG"],
        "dimension_overrides": {},
        "additional_hard_reject_rules": [],
        "additional_review_rules": [],
    }


@pytest.fixture()
def staging_dir(tmp_path, minimal_overlay_dict) -> Path:
    """Temp staging dir pre-populated with TST.json overlay."""
    d = tmp_path / "staging"
    d.mkdir()
    (d / "TST.json").write_text(
        json.dumps(minimal_overlay_dict), encoding="utf-8"
    )
    return d


@pytest.fixture()
def live_ruleset_path(tmp_path, live_ruleset_dict) -> Path:
    """Copy of live ruleset in a temp file — safe to mutate."""
    p = tmp_path / "kyc_rules_v2.0.json"
    p.write_text(json.dumps(live_ruleset_dict, indent=2), encoding="utf-8")
    return p


# ── MRG-001: validate_reviewer accepts valid name ──────────────────────────────

def test_MRG_001_reviewer_valid():
    assert validate_reviewer("Alice Smith") == "Alice Smith"
    assert validate_reviewer("  bob  ") == "bob"


# ── MRG-002: validate_reviewer rejects blank / None ───────────────────────────

def test_MRG_002_reviewer_blank_rejected():
    with pytest.raises(MergeError, match="reviewed_by"):
        validate_reviewer("")
    with pytest.raises(MergeError, match="reviewed_by"):
        validate_reviewer("   ")
    with pytest.raises(MergeError, match="reviewed_by"):
        validate_reviewer(None)


# ── MRG-003: load_staged_overlay succeeds for valid file ──────────────────────

def test_MRG_003_load_staged_overlay(staging_dir):
    overlay = load_staged_overlay("TST", staging_dir=staging_dir)
    assert overlay.jurisdiction_code == "TST"
    assert "TEST-REG" in overlay.regulators


# ── MRG-004: load_staged_overlay raises MergeError for missing file ────────────

def test_MRG_004_load_staged_missing(tmp_path):
    with pytest.raises(MergeError, match="No staged overlay"):
        load_staged_overlay("ZZZ", staging_dir=tmp_path)


# ── MRG-005: apply_overlay_to_dict upserts correctly ──────────────────────────

def test_MRG_005_apply_overlay_upsert(live_ruleset_dict, minimal_overlay_dict):
    from rules.schema.dimensions import JurisdictionOverlay
    overlay = JurisdictionOverlay.model_validate(minimal_overlay_dict)

    # TST is not in live ruleset
    assert "TST" not in live_ruleset_dict.get("jurisdictions", {})

    mutated, is_new = apply_overlay_to_dict(live_ruleset_dict, overlay, "Alice")
    assert is_new is True
    assert "TST" in mutated["jurisdictions"]
    # Changelog entry appended
    last_entry = mutated["changelog"][-1]
    assert last_entry["reviewed_by"] == "Alice"
    assert "add TST" in last_entry["change"]


# ── MRG-006: apply_overlay_to_dict marks is_new=False for existing jurisdiction

def test_MRG_006_apply_overlay_update(live_ruleset_dict):
    from rules.schema.dimensions import JurisdictionOverlay
    # GBR already exists in live ruleset
    assert "GBR" in live_ruleset_dict.get("jurisdictions", {})
    overlay_data = live_ruleset_dict["jurisdictions"]["GBR"].copy()
    overlay = JurisdictionOverlay.model_validate(overlay_data)

    mutated, is_new = apply_overlay_to_dict(live_ruleset_dict, overlay, "Bob")
    assert is_new is False
    last_entry = mutated["changelog"][-1]
    assert "update GBR" in last_entry["change"]
    assert last_entry["reviewed_by"] == "Bob"


# ── MRG-007: merge_staged_overlay dry_run does not write to disk ───────────────

def test_MRG_007_dry_run_no_write(staging_dir, live_ruleset_path):
    mtime_before = live_ruleset_path.stat().st_mtime

    result = merge_staged_overlay(
        "TST",
        reviewed_by="Carol",
        _dry_run=True,
        _staging_dir=staging_dir,
        _ruleset_path=live_ruleset_path,
    )

    assert result.status == "dry_run"
    assert result.jurisdiction_code == "TST"
    assert result.is_new is True
    assert result.reviewed_by == "Carol"
    assert result.error is None
    # File must be untouched
    assert live_ruleset_path.stat().st_mtime == mtime_before


# ── MRG-008: merge_staged_overlay writes to disk when not dry_run ─────────────

def test_MRG_008_real_merge_writes(staging_dir, live_ruleset_path):
    result = merge_staged_overlay(
        "TST",
        reviewed_by="Dana",
        _dry_run=False,
        _staging_dir=staging_dir,
        _ruleset_path=live_ruleset_path,
    )

    assert result.status == "merged"
    # File should now contain TST
    updated = json.loads(live_ruleset_path.read_text())
    assert "TST" in updated["jurisdictions"]
    last_entry = updated["changelog"][-1]
    assert last_entry["reviewed_by"] == "Dana"


# ── MRG-009: merge_staged_overlay rejects blank reviewer ──────────────────────

def test_MRG_009_no_reviewer_rejected(staging_dir, live_ruleset_path):
    with pytest.raises(MergeError, match="reviewed_by"):
        merge_staged_overlay(
            "TST",
            reviewed_by="",
            _dry_run=True,
            _staging_dir=staging_dir,
            _ruleset_path=live_ruleset_path,
        )


# ── MRG-010: merge_all_staged dry_run collects results ────────────────────────

def test_MRG_010_merge_all_staged(staging_dir, live_ruleset_path):
    results = merge_all_staged(
        reviewed_by="Eve",
        _dry_run=True,
        _staging_dir=staging_dir,
        _ruleset_path=live_ruleset_path,
    )
    assert len(results) == 1
    assert results[0].jurisdiction_code == "TST"
    assert results[0].status == "dry_run"
    assert results[0].error is None
