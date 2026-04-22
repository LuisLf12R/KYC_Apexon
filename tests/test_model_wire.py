"""
tests/test_model_wire.py
P7-C — CustomerDecision.model_validate() wired into evaluate_customer().
"""

import pandas as pd
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from kyc_engine.engine import KYCComplianceEngine
from kyc_engine.models import CustomerDecision, DispositionLevel


def _make_engine():
    return KYCComplianceEngine(data_clean_dir=Path("/nonexistent"))


def _wire_clean_customer(engine, customer_id, jurisdiction="USA"):
    engine.customers = pd.DataFrame([{
        "customer_id": customer_id,
        "risk_rating": "LOW",
        "jurisdiction": jurisdiction,
    }])
    engine.screenings = pd.DataFrame([{
        "customer_id": customer_id,
        "screening_date": datetime.now().isoformat(),
        "screening_result": "NO_HIT",
        "list_reference": "OFAC-SDN",
    }])
    engine.id_verifications = pd.DataFrame()
    engine.transactions = pd.DataFrame()
    engine.documents = pd.DataFrame()
    engine.beneficial_owners = pd.DataFrame()


# MW-001: evaluate_customer returns a plain dict, not a Pydantic model instance
def test_mw_001_returns_dict():
    engine = _make_engine()
    _wire_clean_customer(engine, "T001")
    result = engine.evaluate_customer("T001")
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"


# MW-002: result contains all required CustomerDecision fields
def test_mw_002_required_fields_present():
    engine = _make_engine()
    _wire_clean_customer(engine, "T002")
    result = engine.evaluate_customer("T002")
    required = [
        "customer_id", "jurisdiction", "overall_score",
        "aml_screening_score", "identity_verification_score",
        "account_activity_score", "proof_of_address_score",
        "beneficial_ownership_score", "data_quality_score",
        "disposition", "overall_status",
        "triggered_reject_rules", "triggered_review_rules",
        "rationale", "ruleset_version",
    ]
    for field in required:
        assert field in result, f"Missing field: {field}"


# MW-003: disposition is a string in the returned dict (enum serialised by model_dump)
def test_mw_003_disposition_is_string():
    engine = _make_engine()
    _wire_clean_customer(engine, "T003")
    result = engine.evaluate_customer("T003")
    assert isinstance(result["disposition"], str), (
        f"disposition should be str after model_dump, got {type(result['disposition'])}"
    )
    assert result["disposition"] in ("PASS", "PASS_WITH_NOTES", "REVIEW", "REJECT")


# MW-004: result round-trips cleanly through CustomerDecision.model_validate
def test_mw_004_result_validates_cleanly():
    engine = _make_engine()
    _wire_clean_customer(engine, "T004")
    result = engine.evaluate_customer("T004")
    # Should not raise
    decision = CustomerDecision.model_validate(result)
    assert decision.customer_id == "T004"
    assert isinstance(decision.disposition, DispositionLevel)


# MW-005: REJECT disposition survives the model_dump round-trip as string "REJECT"
def test_mw_005_reject_disposition_roundtrip():
    engine = _make_engine()
    engine.customers = pd.DataFrame([{
        "customer_id": "T005",
        "risk_rating": "HIGH",
        "jurisdiction": "USA",
    }])
    engine.screenings = pd.DataFrame([{
        "customer_id": "T005",
        "screening_date": datetime.now().isoformat(),
        "screening_result": "EXACT_MATCH",
        "resolution_status": "RESOLVED_BLOCKED",
        "resolution_date": datetime.now().isoformat(),
        "list_reference": "OFAC-SDN",
        "match_name": "Blocked Entity",
        "match_score": 0.99,
    }])
    engine.id_verifications = pd.DataFrame()
    engine.transactions = pd.DataFrame()
    engine.documents = pd.DataFrame()
    engine.beneficial_owners = pd.DataFrame()

    result = engine.evaluate_customer("T005")
    assert result["disposition"] == "REJECT"
    assert isinstance(result["disposition"], str)


# MW-006: validation failure falls back to raw dict — no exception raised to caller
def test_mw_006_validation_failure_falls_back_gracefully():
    engine = _make_engine()
    _wire_clean_customer(engine, "T006")

    with patch("kyc_engine.engine.CustomerDecision.model_validate", side_effect=ValueError("injected")):
        result = engine.evaluate_customer("T006")

    # Fallback path returns raw dict — must still be a dict with customer_id
    assert isinstance(result, dict)
    assert result["customer_id"] == "T006"
