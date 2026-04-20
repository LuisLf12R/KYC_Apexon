"""
PR generator tests (PR-001 through PR-005).

Regression gate subprocess is mocked — no real pytest run inside tests.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from rules.schema import JurisdictionOverlay


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_overlay(code: str, regulators=None, overrides=None) -> JurisdictionOverlay:
    return JurisdictionOverlay.model_validate({
        "jurisdiction_code": code,
        "regulators": regulators or ["TestReg"],
        "dimension_overrides": overrides or {},
        "additional_hard_reject_rules": [],
        "additional_review_rules": [],
    })


def _mock_subprocess_pass():
    """Subprocess mock that simulates pytest passing."""
    mock = MagicMock()
    mock.return_value.returncode = 0
    mock.return_value.stdout = "111 passed, 2 warnings in 3.10s\n"
    mock.return_value.stderr = ""
    return mock


def _mock_subprocess_fail():
    """Subprocess mock that simulates pytest failure."""
    mock = MagicMock()
    mock.return_value.returncode = 1
    mock.return_value.stdout = "109 passed, 2 failed in 3.50s\n"
    mock.return_value.stderr = ""
    return mock


# ---------------------------------------------------------------------------
# PR-001: diff_overlays classifies new jurisdiction correctly
# ---------------------------------------------------------------------------

def test_pr_001_diff_classifies_new_jurisdiction():
    """PR-001: staged overlay for jurisdiction not in live ruleset is classified new."""
    from sources.pr_generator.pr_generator import diff_overlays
    staged = [_make_overlay("CAN")]
    live = {"jurisdictions": {"USA": {}}}
    result = diff_overlays(staged, live)
    assert len(result["new"]) == 1
    assert result["new"][0].jurisdiction_code == "CAN"
    assert result["modified"] == []
    assert result["unchanged"] == []


# ---------------------------------------------------------------------------
# PR-002: diff_overlays classifies unchanged jurisdiction correctly
# ---------------------------------------------------------------------------

def test_pr_002_diff_classifies_unchanged_jurisdiction():
    """PR-002: staged overlay identical to live is classified unchanged."""
    from sources.pr_generator.pr_generator import diff_overlays
    overlay = _make_overlay("USA", regulators=["FinCEN"])
    live = {"jurisdictions": {"USA": overlay.model_dump(mode="json")}}
    result = diff_overlays([overlay], live)
    assert result["unchanged"][0].jurisdiction_code == "USA"
    assert result["new"] == []
    assert result["modified"] == []


# ---------------------------------------------------------------------------
# PR-003: diff_overlays classifies modified jurisdiction correctly
# ---------------------------------------------------------------------------

def test_pr_003_diff_classifies_modified_jurisdiction():
    """PR-003: staged overlay differing from live is classified modified."""
    from sources.pr_generator.pr_generator import diff_overlays
    staged_overlay = _make_overlay("GBR", overrides={"screening": {"max_screening_age_days": 180}})
    live_overlay = _make_overlay("GBR", overrides={})
    live = {"jurisdictions": {"GBR": live_overlay.model_dump(mode="json")}}
    result = diff_overlays([staged_overlay], live)
    assert result["modified"][0].jurisdiction_code == "GBR"
    assert result["new"] == []
    assert result["unchanged"] == []


# ---------------------------------------------------------------------------
# PR-004: emit_pr_description contains gate status and jurisdiction sections
# ---------------------------------------------------------------------------

def test_pr_004_emit_pr_description_contains_key_sections():
    """PR-004: emitted markdown contains gate badge, new jurisdiction, and merge instructions."""
    from sources.pr_generator.pr_generator import emit_pr_description, diff_overlays
    staged = [_make_overlay("CAN", regulators=["FINTRAC"])]
    live = {"jurisdictions": {}}
    diff = diff_overlays(staged, live)
    md = emit_pr_description(
        diff=diff,
        gate_passed=True,
        n_passed=111,
        n_failed=0,
        summary_line="111 passed in 3.10s",
        staged_overlays=staged,
    )
    assert "✅ PASSED" in md
    assert "CAN" in md
    assert "FINTRAC" in md
    assert "Merge Instructions" in md
    assert "named human reviewer" in md


# ---------------------------------------------------------------------------
# PR-005: generate_pr writes PR_DRAFT.md and returns path
# ---------------------------------------------------------------------------

def test_pr_005_generate_pr_writes_draft_file(tmp_path, monkeypatch):
    """PR-005: generate_pr writes a non-empty PR_DRAFT.md to the output path."""
    import sources.pr_generator.pr_generator as pr_mod
    monkeypatch.setattr(pr_mod, "_STAGING_DIR", tmp_path)
    monkeypatch.setattr(pr_mod, "_LIVE_RULESET",
        Path("rules/kyc_rules_v2.0.json"))

    out_path = tmp_path / "PR_DRAFT.md"

    path = pr_mod.generate_pr(
        output_path=out_path,
        _subprocess_run=_mock_subprocess_pass(),
    )

    assert path == out_path
    assert path.exists()
    content = path.read_text()
    assert "KYC Ruleset" in content
    assert len(content) > 100
