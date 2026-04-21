"""
tests/test_institution.py
Tests for institution overlay model and layering — INST-001 through INST-010
All I/O uses tmp_path — never touches live ruleset or production institution dir.
"""

import json
from pathlib import Path

import pytest

from rules.schema.institution import InstitutionOverlay
from kyc_engine.ruleset import (
    get_institution_params,
    get_jurisdiction_params,
    load_institution_overlay,
    reset_ruleset_cache,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_cache():
    """Reset the ruleset cache before each test."""
    reset_ruleset_cache()
    yield
    reset_ruleset_cache()


@pytest.fixture()
def institution_dir(tmp_path) -> Path:
    d = tmp_path / "institutions"
    d.mkdir()
    return d


def _write_overlay(institution_dir: Path, data: dict) -> None:
    institution_id = data["institution_id"]
    (institution_dir / f"{institution_id}.json").write_text(
        json.dumps(data), encoding="utf-8"
    )


@pytest.fixture()
def gbr_institution_dir(institution_dir) -> Path:
    """Institution dir with a GBR overlay that tightens UBO to 10%."""
    _write_overlay(institution_dir, {
        "institution_id": "BANK001",
        "institution_name": "Test Private Bank",
        "jurisdiction_code": "GBR",
        "dimension_overrides": {
            "beneficial_ownership": {
                "ownership_threshold_pct": 10.0
            }
        },
        "policy_notes": "Wolfsberg-aligned EDD policy",
        "active": True,
    })
    return institution_dir


@pytest.fixture()
def inactive_institution_dir(institution_dir) -> Path:
    """Institution dir with an inactive overlay."""
    _write_overlay(institution_dir, {
        "institution_id": "BANK002",
        "institution_name": "Inactive Bank",
        "jurisdiction_code": "GBR",
        "dimension_overrides": {
            "beneficial_ownership": {
                "ownership_threshold_pct": 5.0
            }
        },
        "active": False,
    })
    return institution_dir


# ── INST-001: InstitutionOverlay validates a complete overlay ──────────────────

def test_INST_001_schema_valid():
    overlay = InstitutionOverlay(
        institution_id="BANK001",
        institution_name="Test Bank",
        jurisdiction_code="GBR",
        dimension_overrides={"beneficial_ownership": {"ownership_threshold_pct": 10.0}},
        policy_notes="Wolfsberg",
        active=True,
    )
    assert overlay.institution_id == "BANK001"
    assert overlay.active is True


# ── INST-002: InstitutionOverlay rejects blank institution_id ─────────────────

def test_INST_002_blank_id_rejected():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        InstitutionOverlay(
            institution_id="",
            institution_name="Test Bank",
            jurisdiction_code="GBR",
        )


# ── INST-003: InstitutionOverlay defaults active=True, overrides={} ───────────

def test_INST_003_defaults():
    overlay = InstitutionOverlay(
        institution_id="BANK999",
        institution_name="Minimal Bank",
        jurisdiction_code="SGP",
    )
    assert overlay.active is True
    assert overlay.dimension_overrides == {}
    assert overlay.policy_notes is None


# ── INST-004: load_institution_overlay reads from disk ────────────────────────

def test_INST_004_load_from_disk(gbr_institution_dir):
    overlay = load_institution_overlay("BANK001", institution_dir=gbr_institution_dir)
    assert overlay.institution_id == "BANK001"
    assert overlay.jurisdiction_code == "GBR"
    assert overlay.dimension_overrides["beneficial_ownership"]["ownership_threshold_pct"] == 10.0


# ── INST-005: load_institution_overlay raises for missing file ────────────────

def test_INST_005_missing_file(institution_dir):
    with pytest.raises(FileNotFoundError, match="BANKXXX"):
        load_institution_overlay("BANKXXX", institution_dir=institution_dir)


# ── INST-006: get_institution_params applies overlay on top of jurisdiction ───

def test_INST_006_layering_gbr(gbr_institution_dir):
    # GBR jurisdiction baseline UBO threshold (from live ruleset or baseline)
    jurisdiction_params = get_jurisdiction_params("GBR")
    baseline_ubo = jurisdiction_params["beneficial_ownership"]["ownership_threshold_pct"]

    # Institution overlay tightens to 10%
    institution_params = get_institution_params(
        "GBR", "BANK001", institution_dir=gbr_institution_dir
    )
    inst_ubo = institution_params["beneficial_ownership"]["ownership_threshold_pct"]

    assert inst_ubo == 10.0
    # Other dimension fields must be preserved from jurisdiction merge
    assert "max_chain_depth" in institution_params["beneficial_ownership"]


# ── INST-007: get_institution_params with no institution_id = jurisdiction params

def test_INST_007_no_institution_id():
    jurisdiction_params = get_jurisdiction_params("GBR")
    result = get_institution_params("GBR", institution_id=None)
    assert result == jurisdiction_params


# ── INST-008: get_institution_params falls back gracefully for missing file ────

def test_INST_008_missing_overlay_fallback(institution_dir):
    # BANKXXX file does not exist — should log warning and return jurisdiction params
    jurisdiction_params = get_jurisdiction_params("GBR")
    result = get_institution_params("GBR", "BANKXXX", institution_dir=institution_dir)
    assert result == jurisdiction_params


# ── INST-009: inactive overlay is not applied ─────────────────────────────────

def test_INST_009_inactive_overlay_skipped(inactive_institution_dir):
    jurisdiction_params = get_jurisdiction_params("GBR")
    result = get_institution_params(
        "GBR", "BANK002", institution_dir=inactive_institution_dir
    )
    # Inactive overlay must not change params
    assert result == jurisdiction_params


# ── INST-010: overlay with empty dimension_overrides returns jurisdiction params

def test_INST_010_empty_overrides(institution_dir):
    _write_overlay(institution_dir, {
        "institution_id": "BANK003",
        "institution_name": "No-Override Bank",
        "jurisdiction_code": "USA",
        "dimension_overrides": {},
        "active": True,
    })
    jurisdiction_params = get_jurisdiction_params("USA")
    result = get_institution_params("USA", "BANK003", institution_dir=institution_dir)
    assert result == jurisdiction_params
