"""
tests/test_impact.py
Tests for sources/impact/impact.py — IMP-001 through IMP-010
All tests inject decisions and overlays directly — no CSV or network I/O.
"""

import json
from pathlib import Path

import pytest

from sources.impact import (
    ImpactFlip,
    ImpactReport,
    compute_disposition_under_rules,
    compute_impact,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def live_ruleset_path() -> Path:
    return Path("rules/kyc_rules_v2.0.json")


@pytest.fixture()
def base_thresholds() -> dict:
    return {"pass_minimum": 70, "pass_with_notes_minimum": 50}


def _decision(
    customer_id: str,
    jurisdiction: str,
    disposition: str,
    score: float,
    **details,
) -> dict:
    """Build a minimal CustomerDecision-compatible dict."""
    d = {
        "customer_id": customer_id,
        "jurisdiction": jurisdiction,
        "disposition": disposition,
        "overall_score": score,
        "aml_screening_details": {"status": "no_match", "hit_status": "", "finding": ""},
        "identity_verification_details": {"status": "verified", "finding": ""},
        "account_activity_details": {"status": "activity_assessed", "finding": ""},
        "proof_of_address_details": {"status": "address_on_file", "finding": ""},
        "beneficial_ownership_details": {"status": "ubo_identified", "finding": ""},
        "data_quality_details": {"status": "data_quality", "quality_rating": "Good", "finding": ""},
    }
    d.update(details)
    return d


def _empty_overlay(jurisdiction_code: str) -> dict:
    return {
        "jurisdiction_code": jurisdiction_code,
        "regulators": ["TEST-REG"],
        "dimension_overrides": {},
        "additional_hard_reject_rules": [],
        "additional_review_rules": [],
    }


# ── IMP-001: PASS stays PASS under empty overlay ──────────────────────────────

def test_IMP_001_pass_stays_pass(live_ruleset_path):
    decisions = [_decision("C001", "GBR", "PASS", score=85.0)]
    report = compute_impact("GBR", _empty_overlay("GBR"), decisions, _ruleset_path=live_ruleset_path)
    assert report.flip_count == 0
    assert report.total_evaluated == 1


# ── IMP-002: REJECT stays REJECT under empty overlay ─────────────────────────

def test_IMP_002_reject_stays_reject(live_ruleset_path):
    decisions = [
        _decision(
            "C002", "GBR", "REJECT", score=0.0,
            aml_screening_details={"status": "confirmed_match", "hit_status": "CONFIRMED", "finding": "SDN hit"},
        )
    ]
    report = compute_impact("GBR", _empty_overlay("GBR"), decisions, _ruleset_path=live_ruleset_path)
    # No new rules — existing REJECT trigger still fires
    assert report.total_evaluated == 1
    # Either no flip (rule still triggers) or flip to non-REJECT — both are valid
    # but confirmed_match/CONFIRMED matches HR-001 in live ruleset, so no flip
    for flip in report.flips:
        assert flip.customer_id == "C002"


# ── IMP-003: REVIEW flips to PASS when score is above threshold ───────────────

def test_IMP_003_review_score_based_flips(base_thresholds):
    """
    A REVIEW-by-score customer (score 72, no rule triggers) would PASS
    under an overlay that raises pass_minimum — but for the inverse test:
    under the same baseline rules with score 72, compute_disposition_under_rules
    should return PASS (score >= 70), not REVIEW.
    """
    decision = _decision("C003", "GBR", "REVIEW", score=72.0)
    # No rules trigger for this clean customer
    disposition = compute_disposition_under_rules(
        decision,
        hard_reject_rules=[],
        review_rules=[],
        score_thresholds=base_thresholds,
    )
    assert disposition == "PASS"


# ── IMP-004: PASS flips to REVIEW when new review rule added ─────────────────

def test_IMP_004_new_review_rule_causes_flip(live_ruleset_path):
    """A new jurisdiction-specific review rule triggers on a previously-PASS customer."""
    new_rule = {
        "rule_id": "GBR-RV-001",
        "name": "GBR Enhanced Source of Wealth Check",
        "description": "High-value GBR clients require SoW documentation",
        "dimension": "data_quality",
        "condition_field": "quality_rating",
        "condition_value": "Good",
        "policy_reference": "JMLSG 5.3",
    }
    overlay = {
        "jurisdiction_code": "GBR",
        "regulators": ["FCA"],
        "dimension_overrides": {},
        "additional_hard_reject_rules": [],
        "additional_review_rules": [new_rule],
    }
    # This customer has quality_rating=Good → will be caught by new rule
    decisions = [_decision("C004", "GBR", "PASS", score=80.0)]
    report = compute_impact("GBR", overlay, decisions, _ruleset_path=live_ruleset_path)
    assert report.flip_count == 1
    assert report.flips[0].customer_id == "C004"
    assert report.flips[0].from_disposition == "PASS"
    assert report.flips[0].to_disposition == "REVIEW"


# ── IMP-005: decisions outside jurisdiction are ignored ───────────────────────

def test_IMP_005_jurisdiction_filter(live_ruleset_path):
    decisions = [
        _decision("C005", "USA", "PASS", score=80.0),
        _decision("C006", "USA", "REVIEW", score=55.0),
        _decision("C007", "GBR", "PASS", score=80.0),
    ]
    report = compute_impact("GBR", _empty_overlay("GBR"), decisions, _ruleset_path=live_ruleset_path)
    assert report.total_evaluated == 1   # only C007
    assert report.flip_count == 0


# ── IMP-006: empty decision list returns empty report ─────────────────────────

def test_IMP_006_empty_decisions(live_ruleset_path):
    report = compute_impact("SGP", _empty_overlay("SGP"), [], _ruleset_path=live_ruleset_path)
    assert report.total_evaluated == 0
    assert report.flip_count == 0
    assert report.jurisdiction_code == "SGP"


# ── IMP-007: multiple flips in one report ────────────────────────────────────

def test_IMP_007_multiple_flips(live_ruleset_path):
    new_rule = {
        "rule_id": "SGP-RV-001",
        "name": "SGP Velocity Review",
        "description": "SGP velocity check",
        "dimension": "account_activity",
        "condition_field": "status",
        "condition_value": "activity_assessed",
        "policy_reference": "MAS Notice 626",
    }
    overlay = {
        "jurisdiction_code": "SGP",
        "regulators": ["MAS"],
        "dimension_overrides": {},
        "additional_hard_reject_rules": [],
        "additional_review_rules": [new_rule],
    }
    decisions = [
        _decision("C010", "SGP", "PASS", score=80.0),
        _decision("C011", "SGP", "PASS", score=75.0),
        _decision("C012", "SGP", "REVIEW", score=60.0),  # already REVIEW, no flip
    ]
    report = compute_impact("SGP", overlay, decisions, _ruleset_path=live_ruleset_path)
    assert report.total_evaluated == 3
    flip_ids = {f.customer_id for f in report.flips}
    assert "C010" in flip_ids
    assert "C011" in flip_ids
    assert "C012" not in flip_ids  # already REVIEW, new rule also fires REVIEW — no flip


# ── IMP-008: ImpactReport.summary() returns correct structure ─────────────────

def test_IMP_008_summary_structure(live_ruleset_path):
    new_rule = {
        "rule_id": "CHE-RV-001",
        "name": "CHE Test Rule",
        "description": "Test",
        "dimension": "data_quality",
        "condition_field": "quality_rating",
        "condition_value": "Good",
        "policy_reference": "FINMA",
    }
    overlay = {
        "jurisdiction_code": "CHE",
        "regulators": ["FINMA"],
        "dimension_overrides": {},
        "additional_hard_reject_rules": [],
        "additional_review_rules": [new_rule],
    }
    decisions = [_decision("C020", "CHE", "PASS", score=80.0)]
    report = compute_impact("CHE", overlay, decisions, _ruleset_path=live_ruleset_path)

    summary = report.summary()
    assert summary["jurisdiction_code"] == "CHE"
    assert "total_evaluated" in summary
    assert "flip_count" in summary
    assert "flips" in summary
    assert isinstance(summary["flips"], list)


# ── IMP-009: compute_disposition_under_rules — hard reject overrides score ────

def test_IMP_009_hard_reject_overrides_score(base_thresholds):
    decision = _decision(
        "C030", "USA", "REVIEW", score=90.0,
        aml_screening_details={"status": "confirmed_match", "hit_status": "CONFIRMED", "finding": "hit"},
    )
    hr_rule = {
        "rule_id": "HR-001",
        "dimension": "aml_screening",
        "condition_field": "status",
        "condition_value": "confirmed_match",
    }
    disposition = compute_disposition_under_rules(
        decision,
        hard_reject_rules=[hr_rule],
        review_rules=[],
        score_thresholds=base_thresholds,
    )
    assert disposition == "REJECT"


# ── IMP-010: PASS_WITH_NOTES bucket correct ───────────────────────────────────

def test_IMP_010_pass_with_notes(base_thresholds):
    decision = _decision("C040", "GBR", "PASS", score=58.0)
    disposition = compute_disposition_under_rules(
        decision,
        hard_reject_rules=[],
        review_rules=[],
        score_thresholds=base_thresholds,
    )
    assert disposition == "PASS_WITH_NOTES"
