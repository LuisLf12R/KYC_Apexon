"""
tests/test_sow.py
P7-F — Source of Wealth dimension and engine wire-up.
"""

import pandas as pd
import pytest
from datetime import datetime, date
from pathlib import Path

from kyc_engine.dimensions.source_of_wealth import SourceOfWealthDimension
from rules.schema.dimensions import SoWParameters


def _params(
    categories=None,
    min_docs=1,
    max_age=365,
):
    return SoWParameters(
        accepted_sow_categories=categories or [
            "employment_income", "inheritance", "investment_returns",
            "business_proceeds", "property_sale",
        ],
        min_evidence_docs=min_docs,
        max_evidence_age_days=max_age,
    )


def _customer_df(customer_id, sow_declared=None):
    row = {"customer_id": customer_id, "risk_rating": "LOW", "jurisdiction": "USA"}
    if sow_declared is not None:
        row["sow_declared"] = sow_declared
    return pd.DataFrame([row])


def _sow_doc(customer_id, issue_date=None):
    return pd.DataFrame([{
        "customer_id": customer_id,
        "document_category": "SOW",
        "document_type": "bank_statement",
        "issue_date": issue_date or date.today().isoformat(),
    }])


# SOW-001: not_declared when sow_declared missing from record
def test_sow_001_not_declared():
    dim = SourceOfWealthDimension(_params())
    data = {
        "customers": _customer_df("C001"),
        "documents": pd.DataFrame(),
    }
    result = dim.evaluate("C001", data)
    assert result["sow_status"] == "sow_not_declared"
    assert result["score"] == 20
    assert result["passed"] is False


# SOW-002: unrecognized category
def test_sow_002_unrecognized_category():
    dim = SourceOfWealthDimension(_params())
    data = {
        "customers": _customer_df("C002", sow_declared="lottery_winnings"),
        "documents": pd.DataFrame(),
    }
    result = dim.evaluate("C002", data)
    assert result["sow_status"] == "sow_category_unrecognized"
    assert result["score"] == 50
    assert result["passed"] is False


# SOW-003: declared + recognized but no evidence docs
def test_sow_003_declared_no_evidence():
    dim = SourceOfWealthDimension(_params())
    data = {
        "customers": _customer_df("C003", sow_declared="employment_income"),
        "documents": pd.DataFrame(),
    }
    result = dim.evaluate("C003", data)
    assert result["sow_status"] == "sow_declared_no_evidence"
    assert result["score"] == 60
    assert result["passed"] is False


# SOW-004: fully verified — declaration + recognized + fresh evidence
def test_sow_004_verified():
    dim = SourceOfWealthDimension(_params())
    data = {
        "customers": _customer_df("C004", sow_declared="inheritance"),
        "documents": _sow_doc("C004"),
    }
    result = dim.evaluate("C004", data)
    assert result["sow_status"] == "sow_verified"
    assert result["score"] == 90
    assert result["passed"] is True


# SOW-005: stale evidence doc triggers sow_declared_no_evidence
def test_sow_005_stale_evidence():
    dim = SourceOfWealthDimension(_params(max_age=30))
    data = {
        "customers": _customer_df("C005", sow_declared="employment_income"),
        "documents": _sow_doc("C005", issue_date="2020-01-01"),  # very old
    }
    result = dim.evaluate("C005", data)
    assert result["sow_status"] == "sow_declared_no_evidence"
    assert result["passed"] is False


# SOW-006: score field always present
def test_sow_006_score_always_present():
    dim = SourceOfWealthDimension(_params())
    for sow in [None, "employment_income", "unknown_category"]:
        data = {
            "customers": _customer_df("CX", sow_declared=sow),
            "documents": pd.DataFrame(),
        }
        result = dim.evaluate("CX", data)
        assert "score" in result, f"score missing for sow_declared={sow}"


# SOW-007: engine evaluate_customer includes source_of_wealth_score
def test_sow_007_engine_includes_sow_score():
    from kyc_engine.engine import KYCComplianceEngine
    engine = KYCComplianceEngine(data_clean_dir=Path("/nonexistent"))
    engine.customers = pd.DataFrame([{
        "customer_id": "T007",
        "risk_rating": "LOW",
        "jurisdiction": "USA",
        "sow_declared": "employment_income",
    }])
    engine.screenings = pd.DataFrame([{
        "customer_id": "T007",
        "screening_date": datetime.now().isoformat(),
        "screening_result": "NO_HIT",
        "list_reference": "OFAC-SDN",
    }])
    engine.id_verifications = pd.DataFrame()
    engine.transactions = pd.DataFrame()
    engine.documents = _sow_doc("T007")
    engine.beneficial_owners = pd.DataFrame()
    engine.ubo = pd.DataFrame()

    result = engine.evaluate_customer("T007")
    assert "source_of_wealth_score" in result, "source_of_wealth_score missing from result"
    assert isinstance(result["source_of_wealth_score"], float)
    assert result["source_of_wealth_score"] > 0


# SOW-008: overall_score includes SoW contribution
def test_sow_008_overall_score_includes_sow():
    from kyc_engine.engine import KYCComplianceEngine
    engine = KYCComplianceEngine(data_clean_dir=Path("/nonexistent"))

    def _make_result(sow_declared):
        engine.customers = pd.DataFrame([{
            "customer_id": "T008",
            "risk_rating": "LOW",
            "jurisdiction": "USA",
            "sow_declared": sow_declared,
        }])
        engine.screenings = pd.DataFrame([{
            "customer_id": "T008",
            "screening_date": datetime.now().isoformat(),
            "screening_result": "NO_HIT",
            "list_reference": "OFAC-SDN",
        }])
        engine.id_verifications = pd.DataFrame()
        engine.transactions = pd.DataFrame()
        engine.documents = pd.DataFrame()
        engine.beneficial_owners = pd.DataFrame()
        engine.ubo = pd.DataFrame()
        return engine.evaluate_customer("T008")

    score_with = _make_result("employment_income")
    score_without = _make_result(None)
    # Customer with SoW declaration should score higher overall
    assert score_with["overall_score"] > score_without["overall_score"], (
        f"Expected declared SoW to raise score: "
        f"{score_with['overall_score']} vs {score_without['overall_score']}"
    )
