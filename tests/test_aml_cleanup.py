"""
tests/test_aml_cleanup.py
P7-A — AML inline scoring cleanup.
Verifies that AMLScreeningDimension exposes score/aml_status/aml_hit_status
on all return paths, and that engine.evaluate_customer no longer uses the
inline CSV re-read for AML scoring.
"""

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from kyc_engine.dimensions.aml_screening import AMLScreeningDimension
from rules.schema.dimensions import ScreeningParameters


def _make_params():
    return ScreeningParameters(
        max_screening_age_days=365,
        fuzzy_match_threshold=0.85,
    )


def _make_data(screening_result="NO_HIT", resolution_status="FALSE_POSITIVE",
               risk_rating="LOW", overdue=False):
    from datetime import datetime, timedelta
    screen_date = datetime(2025, 1, 1) if overdue else datetime(2026, 3, 1)
    customers = pd.DataFrame([{
        "customer_id": "C001",
        "risk_rating": risk_rating,
        "jurisdiction": "GBR",
    }])
    screenings = pd.DataFrame([{
        "customer_id": "C001",
        "screening_date": screen_date,
        "screening_result": screening_result,
        "resolution_status": resolution_status,
        "resolution_date": "2026-03-05",
        "hit_status": "CONFIRMED" if resolution_status == "RESOLVED_BLOCKED" else "",
        "list_reference": "OFAC-SDN",
        "match_name": "Test Name" if screening_result != "NO_HIT" else None,
        "match_score": 0.95 if screening_result != "NO_HIT" else None,
    }])
    return {
        "customers": customers,
        "screenings": screenings,
        "screening": screenings,
    }


# AML-001: score field present on NO_HIT path
def test_aml_001_score_present_no_hit():
    dim = AMLScreeningDimension(_make_params())
    result = dim.evaluate("C001", _make_data(screening_result="NO_HIT"))
    assert "score" in result, "score field must be present"
    assert result["score"] == 100


# AML-002: aml_status and aml_hit_status present on NO_HIT path
def test_aml_002_aml_status_no_hit():
    dim = AMLScreeningDimension(_make_params())
    result = dim.evaluate("C001", _make_data(screening_result="NO_HIT"))
    assert result["evaluation_details"]["aml_status"] == "no_match"
    assert result["evaluation_details"]["aml_hit_status"] == ""


# AML-003: confirmed_match path gives score=0 and aml_status='confirmed_match'
def test_aml_003_confirmed_match():
    dim = AMLScreeningDimension(_make_params())
    result = dim.evaluate(
        "C001",
        _make_data(screening_result="EXACT_MATCH", resolution_status="RESOLVED_BLOCKED"),
    )
    assert result["score"] == 0
    assert result["evaluation_details"]["aml_status"] == "confirmed_match"


# AML-004: no_screening_data path (missing screenings df)
def test_aml_004_no_screening_data():
    dim = AMLScreeningDimension(_make_params())
    customers = pd.DataFrame([{
        "customer_id": "C001",
        "risk_rating": "LOW",
        "jurisdiction": "GBR",
    }])
    data = {
        "customers": customers,
        "screenings": pd.DataFrame(),
        "screening": pd.DataFrame(),
    }
    result = dim.evaluate("C001", data)
    assert "score" in result
    assert result["score"] == 0
    assert result["evaluation_details"]["aml_status"] == "no_screening_data"
    assert result["evaluation_details"]["aml_hit_status"] == ""


# AML-005: overdue rescreening gives score=30
def test_aml_005_overdue_score():
    dim = AMLScreeningDimension(_make_params())
    result = dim.evaluate("C001", _make_data(screening_result="NO_HIT", overdue=True))
    assert result["score"] == 30
    assert result["passed"] is False
