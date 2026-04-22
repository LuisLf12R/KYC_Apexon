"""
tests/test_crs_fatca.py
P7-H — CRS/FATCA dimension and engine wire-up.
"""

import pandas as pd
import pytest
from datetime import datetime
from pathlib import Path

from kyc_engine.dimensions.crs_fatca import CRSFATCADimension
from rules.schema.dimensions import CRSFATCAParameters


def _params():
    return CRSFATCAParameters(
        fatca_applicable_jurisdictions=["USA"],
        crs_participating_jurisdictions=["GBR", "CHE", "SGP"],
        w8_w9_required_entity_types=["INDIVIDUAL", "LEGAL_ENTITY"],
    )


def _customer(customer_id, jurisdiction, entity_type="INDIVIDUAL",
              crs_self_cert=None, fatca_status=None, w8w9=None):
    row = {
        "customer_id": customer_id,
        "jurisdiction": jurisdiction,
        "entity_type": entity_type,
        "risk_rating": "LOW",
    }
    if crs_self_cert is not None:
        row["crs_self_cert_on_file"] = crs_self_cert
    if fatca_status is not None:
        row["fatca_status"] = fatca_status
    if w8w9 is not None:
        row["w8_w9_on_file"] = w8w9
    return {"customers": pd.DataFrame([row]), "documents": pd.DataFrame()}


# CRS-001: not_applicable for out-of-scope jurisdiction
def test_crs_001_not_applicable():
    dim = CRSFATCADimension(_params())
    result = dim.evaluate("C001", _customer("C001", "AUS"))
    assert result["crs_fatca_status"] == "not_applicable"
    assert result["passed"] is True
    assert result["score"] == 90


# CRS-002: CRS cert missing triggers crs_cert_missing
def test_crs_002_crs_cert_missing():
    dim = CRSFATCADimension(_params())
    result = dim.evaluate("C002", _customer("C002", "GBR"))
    assert result["crs_fatca_status"] == "crs_cert_missing"
    assert result["passed"] is False
    assert result["score"] == 50


# CRS-003: CRS cert present — passes
def test_crs_003_crs_cert_present():
    dim = CRSFATCADimension(_params())
    result = dim.evaluate(
        "C003",
        _customer("C003", "GBR", crs_self_cert="Y"),
    )
    assert result["crs_fatca_status"] == "crs_and_fatca_ok"
    assert result["passed"] is True


# CRS-004: FATCA jurisdiction, no W-8/W-9 — triggers w8_w9_missing
def test_crs_004_w8_w9_missing():
    dim = CRSFATCADimension(_params())
    result = dim.evaluate("C004", _customer("C004", "USA"))
    assert result["crs_fatca_status"] == "w8_w9_missing"
    assert result["passed"] is False


# CRS-005: FATCA jurisdiction, fatca_status=w9_on_file — passes
def test_crs_005_fatca_w9_on_file():
    dim = CRSFATCADimension(_params())
    result = dim.evaluate(
        "C005",
        _customer("C005", "USA", fatca_status="w9_on_file"),
    )
    assert result["crs_fatca_status"] == "crs_and_fatca_ok"
    assert result["passed"] is True


# CRS-006: FATCA jurisdiction, w8_w9_on_file=Y fallback — passes
def test_crs_006_fatca_w8w9_flag():
    dim = CRSFATCADimension(_params())
    result = dim.evaluate(
        "C006",
        _customer("C006", "USA", w8w9="Y"),
    )
    assert result["crs_fatca_status"] == "crs_and_fatca_ok"
    assert result["passed"] is True


# CRS-007: score field always present
def test_crs_007_score_always_present():
    dim = CRSFATCADimension(_params())
    for jur in ["GBR", "USA", "AUS"]:
        result = dim.evaluate("CX", _customer("CX", jur))
        assert "score" in result, f"score missing for jurisdiction={jur}"


# CRS-008: engine result includes crs_fatca_score
def test_crs_008_engine_includes_crs_score():
    from kyc_engine.engine import KYCComplianceEngine
    engine = KYCComplianceEngine(data_clean_dir=Path("/nonexistent"))
    engine.customers = pd.DataFrame([{
        "customer_id": "T008",
        "risk_rating": "LOW",
        "jurisdiction": "GBR",
        "entity_type": "INDIVIDUAL",
        "crs_self_cert_on_file": "Y",
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

    result = engine.evaluate_customer("T008")
    assert "crs_fatca_score" in result
    assert isinstance(result["crs_fatca_score"], float)
