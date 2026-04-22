"""
tests/test_ubo_traversal.py
P7-E — UBO graph traversal, threshold fix, score field.
"""

import pandas as pd
import pytest
from kyc_engine.dimensions.beneficial_ownership import BeneficialOwnershipDimension
from rules.schema.dimensions import BeneficialOwnershipParameters


def _params(threshold=25.0, max_depth=4):
    return BeneficialOwnershipParameters(
        ownership_threshold_pct=threshold,
        max_chain_depth=max_depth,
    )


def _base_data(customer_id, ubos_rows, jurisdiction="USA", risk="LOW"):
    customers = pd.DataFrame([{
        "customer_id": customer_id,
        "entity_type": "LEGAL_ENTITY",
        "jurisdiction": jurisdiction,
        "risk_rating": risk,
    }])
    ubo_df = pd.DataFrame(ubos_rows) if ubos_rows else pd.DataFrame(
        columns=["customer_id", "ubo_name", "ownership_percent"]
    )
    return {
        "customers": customers,
        "ubo": ubo_df,
        "screenings": pd.DataFrame(columns=["match_name"]),
    }


# UBO-T-001: score field present on compliant result
def test_ubo_t_001_score_present_compliant():
    dim = BeneficialOwnershipDimension(_params())
    data = _base_data("C001", [{
        "customer_id": "C001",
        "ubo_name": "Alice",
        "ubo_dob": "1980-01-01",
        "ubo_nationality": "US",
        "ownership_percent": 100,
        "verification_date": "2025-01-01",
    }])
    result = dim.evaluate("C001", data)
    assert "score" in result
    assert isinstance(result["score"], int)
    assert result["score"] > 0


# UBO-T-002: score field present on missing UBO result
def test_ubo_t_002_score_present_missing():
    dim = BeneficialOwnershipDimension(_params())
    data = _base_data("C002", [])
    result = dim.evaluate("C002", data)
    assert "score" in result
    assert result["score"] == 10  # NON_COMPLIANT_UBO_MISSING


# UBO-T-003: threshold sourced from params, not hardcoded dict
# HKG threshold = 10% via params; single UBO at 15% must PASS
def test_ubo_t_003_threshold_from_params():
    dim = BeneficialOwnershipDimension(_params(threshold=10.0))
    data = _base_data("C003", [{
        "customer_id": "C003",
        "ubo_name": "Bob",
        "ubo_dob": "1975-06-01",
        "ubo_nationality": "HK",
        "ownership_percent": 15,
        "verification_date": "2025-01-01",
    }], jurisdiction="HKG")
    result = dim.evaluate("C003", data)
    # 15% >= 10% threshold -> ownership check should pass
    ownership_findings = [f for f in result["findings"] if "Effective ownership" in f]
    assert any("PASS" in f for f in ownership_findings), (
        f"Expected ownership PASS finding, got: {result['findings']}"
    )


# UBO-T-004: record beyond max_chain_depth is excluded and flagged
def test_ubo_t_004_chain_depth_exclusion():
    dim = BeneficialOwnershipDimension(_params(threshold=25.0, max_depth=2))
    data = _base_data("C004", [
        {
            "customer_id": "C004",
            "ubo_name": "DirectOwner",
            "ubo_dob": "1980-01-01",
            "ubo_nationality": "US",
            "ownership_percent": 60,
            "verification_date": "2025-01-01",
            "chain_depth": 0,
        },
        {
            "customer_id": "C004",
            "ubo_name": "DeepOwner",
            "ubo_dob": "1985-01-01",
            "ubo_nationality": "US",
            "ownership_percent": 40,
            "verification_date": "2025-01-01",
            "chain_depth": 3,  # exceeds max_depth=2 -> excluded
        },
    ])
    result = dim.evaluate("C004", data)
    exclusion_findings = [f for f in result["findings"] if "excluded" in f.lower()]
    assert exclusion_findings, (
        f"Expected exclusion finding for deep record, got: {result['findings']}"
    )


# UBO-T-005: indirect ownership uses parent_ownership_pct for effective calc
def test_ubo_t_005_indirect_ownership_effective_pct():
    dim = BeneficialOwnershipDimension(_params(threshold=25.0, max_depth=4))
    # Direct: 60%. Indirect: 50% of a parent that owns 50% -> effective 25%.
    # Total effective = 60 + 25 = 85% >= 25% threshold.
    ubos = [
        {
            "customer_id": "C005",
            "ubo_name": "DirectOwner",
            "ubo_dob": "1980-01-01",
            "ubo_nationality": "US",
            "ownership_percent": 60,
            "verification_date": "2025-01-01",
            "chain_depth": 0,
        },
        {
            "customer_id": "C005",
            "ubo_name": "IndirectOwner",
            "ubo_dob": "1985-01-01",
            "ubo_nationality": "US",
            "ownership_percent": 50,
            "parent_ownership_pct": 50,  # effective = 50 * 50 / 100 = 25
            "verification_date": "2025-01-01",
            "chain_depth": 1,
        },
    ]
    dim2 = BeneficialOwnershipDimension(_params(threshold=25.0, max_depth=4))
    included, excluded, effective_total = dim2._resolve_effective_ownership(ubos)
    assert excluded == 0
    assert abs(effective_total - 85.0) < 0.01, f"Expected 85.0, got {effective_total}"


# UBO-T-006: N/A path (individual) still returns score field
def test_ubo_t_006_individual_na_has_score():
    dim = BeneficialOwnershipDimension(_params())
    customers = pd.DataFrame([{
        "customer_id": "C006",
        "entity_type": "INDIVIDUAL",
        "jurisdiction": "USA",
        "risk_rating": "LOW",
    }])
    data = {
        "customers": customers,
        "ubo": pd.DataFrame(),
        "screenings": pd.DataFrame(),
    }
    result = dim.evaluate("C006", data)
    assert "score" in result
    assert result["passed"] is True
