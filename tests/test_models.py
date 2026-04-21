"""
tests/test_models.py
Tests for kyc_engine/models.py — MOD-001 through MOD-010
"""

import pytest
from pydantic import ValidationError

from kyc_engine.models import (
    AMLScreeningDetails,
    CustomerDecision,
    DataQualityDetails,
    DimensionDetails,
    DispositionLevel,
    DispositionResult,
    TriggeredRule,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _minimal_decision(**overrides) -> dict:
    base = {
        "customer_id": "C001",
        "jurisdiction": "GBR",
        "overall_score": 72.5,
        "aml_screening_score": 100.0,
        "identity_verification_score": 80.0,
        "account_activity_score": 70.0,
        "proof_of_address_score": 60.0,
        "beneficial_ownership_score": 80.0,
        "data_quality_score": 90.0,
        "aml_screening_details": {"status": "no_match", "hit_status": "", "finding": "Clear"},
        "identity_verification_details": {"status": "verified", "finding": "Passport OK"},
        "account_activity_details": {"status": "activity_assessed", "finding": ""},
        "proof_of_address_details": {"status": "address_on_file", "finding": ""},
        "beneficial_ownership_details": {"status": "ubo_identified", "finding": ""},
        "data_quality_details": {"status": "data_quality", "quality_rating": "Good", "finding": ""},
        "dimension_results": {},
        "disposition": "PASS",
        "overall_status": "PASS",
        "triggered_reject_rules": [],
        "triggered_review_rules": [],
        "rationale": "Score 72.5/100 meets threshold.",
        "ruleset_version": "kyc-rules-v2.1",
        "evaluation_date": "2025-01-01T00:00:00",
    }
    base.update(overrides)
    return base


# ── MOD-001: DispositionLevel enum values ──────────────────────────────────────

def test_MOD_001_disposition_level_values():
    assert DispositionLevel.PASS == "PASS"
    assert DispositionLevel.REJECT == "REJECT"
    assert DispositionLevel.REVIEW == "REVIEW"
    assert DispositionLevel.PASS_WITH_NOTES == "PASS_WITH_NOTES"


# ── MOD-002: DispositionLevel severity ordering ────────────────────────────────

def test_MOD_002_disposition_severity_order():
    assert DispositionLevel.REJECT.is_more_severe_than(DispositionLevel.REVIEW)
    assert DispositionLevel.REVIEW.is_more_severe_than(DispositionLevel.PASS_WITH_NOTES)
    assert DispositionLevel.PASS_WITH_NOTES.is_more_severe_than(DispositionLevel.PASS)
    assert not DispositionLevel.PASS.is_more_severe_than(DispositionLevel.REJECT)


# ── MOD-003: TriggeredRule validates correctly ─────────────────────────────────

def test_MOD_003_triggered_rule_valid():
    r = TriggeredRule(
        rule_id="HR-001",
        name="Confirmed Sanctions Match",
        description="Customer appears on OFAC SDN list",
        policy_reference="OFAC/SDN",
        dimension="aml_screening",
    )
    assert r.rule_id == "HR-001"
    assert r.policy_reference == "OFAC/SDN"


def test_MOD_003b_triggered_rule_optional_policy_ref():
    r = TriggeredRule(rule_id="RV-001", name="PEP", description="PEP flag", dimension="screening")
    assert r.policy_reference == ""


# ── MOD-004: DimensionDetails base and subclasses ─────────────────────────────

def test_MOD_004_dimension_details():
    d = DimensionDetails(status="verified", finding="Passport OK")
    assert d.status == "verified"


def test_MOD_004b_aml_details():
    a = AMLScreeningDetails(status="no_match", hit_status="", finding="Clear")
    assert a.hit_status == ""


def test_MOD_004c_dq_details():
    dq = DataQualityDetails(status="data_quality", quality_rating="Good", finding="")
    assert dq.quality_rating == "Good"


# ── MOD-005: CustomerDecision validates a PASS result ─────────────────────────

def test_MOD_005_customer_decision_pass():
    cd = CustomerDecision.model_validate(_minimal_decision())
    assert cd.customer_id == "C001"
    assert cd.disposition == DispositionLevel.PASS
    assert cd.overall_status == DispositionLevel.PASS
    assert not cd.is_rejected
    assert not cd.requires_review


# ── MOD-006: CustomerDecision validates a REJECT result ───────────────────────

def test_MOD_006_customer_decision_reject():
    reject_rule = {
        "rule_id": "HR-001",
        "name": "Confirmed Sanctions Match",
        "description": "OFAC hit",
        "policy_reference": "OFAC",
        "dimension": "aml_screening",
    }
    cd = CustomerDecision.model_validate(
        _minimal_decision(
            disposition="REJECT",
            overall_status="REJECT",
            aml_screening_score=0.0,
            overall_score=18.0,
            triggered_reject_rules=[reject_rule],
            rationale="Hard rejection: confirmed sanctions match.",
        )
    )
    assert cd.disposition == DispositionLevel.REJECT
    assert cd.is_rejected
    assert cd.requires_review
    assert len(cd.triggered_reject_rules) == 1
    assert cd.triggered_reject_rules[0].rule_id == "HR-001"


# ── MOD-007: CustomerDecision validates a REVIEW result ───────────────────────

def test_MOD_007_customer_decision_review():
    review_rule = {
        "rule_id": "RV-001",
        "name": "PEP Detected",
        "description": "PEP flag",
        "policy_reference": "",
        "dimension": "screening",
    }
    cd = CustomerDecision.model_validate(
        _minimal_decision(
            disposition="REVIEW",
            overall_status="REVIEW",
            triggered_review_rules=[review_rule],
            rationale="Manual review required.",
        )
    )
    assert cd.requires_review
    assert not cd.is_rejected
    assert len(cd.triggered_review_rules) == 1


# ── MOD-008: Score out-of-range raises ValidationError ────────────────────────

def test_MOD_008_score_out_of_range():
    with pytest.raises(ValidationError):
        CustomerDecision.model_validate(_minimal_decision(overall_score=150.0))

    with pytest.raises(ValidationError):
        CustomerDecision.model_validate(_minimal_decision(aml_screening_score=-5.0))


# ── MOD-009: DispositionResult validates determine_disposition output ──────────

def test_MOD_009_disposition_result():
    raw = {
        "disposition": "REVIEW",
        "triggered_reject_rules": [],
        "triggered_review_rules": [
            {
                "rule_id": "RV-SCORE",
                "name": "Score Below Minimum",
                "description": "Score 45 below floor",
                "policy_reference": "Scoring Policy 1.1",
                "dimension": "composite",
            }
        ],
        "rationale": "Score below threshold.",
        "ruleset_version": "kyc-rules-v2.1",
    }
    dr = DispositionResult.model_validate(raw)
    assert dr.disposition == DispositionLevel.REVIEW
    assert len(dr.triggered_review_rules) == 1


# ── MOD-010: Extra fields are silently ignored (extra="ignore") ───────────────

def test_MOD_010_extra_fields_ignored():
    data = _minimal_decision()
    data["unexpected_future_field"] = "ignored"
    data["another_extra"] = 42
    cd = CustomerDecision.model_validate(data)
    assert cd.customer_id == "C001"
