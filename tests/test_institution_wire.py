"""
tests/test_institution_wire.py
P7-B — institution overlay wire-up into evaluate_customer().
Verifies that institution_id=None preserves existing behaviour and
that a non-None institution_id causes get_institution_params to be
called instead of get_jurisdiction_params.
"""

import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from kyc_engine.engine import KYCComplianceEngine


def _make_engine():
    return KYCComplianceEngine(data_clean_dir=Path("/nonexistent"))


def _minimal_screenings(customer_id):
    from datetime import datetime
    return pd.DataFrame([{
        "customer_id": customer_id,
        "screening_date": datetime.now().isoformat(),
        "screening_result": "NO_HIT",
        "list_reference": "OFAC-SDN",
    }])


def _minimal_customers(customer_id, jurisdiction="USA"):
    return pd.DataFrame([{
        "customer_id": customer_id,
        "risk_rating": "LOW",
        "jurisdiction": jurisdiction,
    }])


# INST-W-001: institution_id=None uses get_jurisdiction_params (default path)
def test_inst_w_001_none_uses_jurisdiction_params():
    engine = _make_engine()
    engine.customers = _minimal_customers("T001")
    engine.screenings = _minimal_screenings("T001")
    engine.id_verifications = pd.DataFrame()
    engine.transactions = pd.DataFrame()
    engine.documents = pd.DataFrame()
    engine.beneficial_owners = pd.DataFrame()

    with patch("kyc_engine.engine.get_jurisdiction_params") as mock_jur, \
         patch("kyc_engine.engine.get_institution_params") as mock_inst:
        mock_jur.return_value = {
            "screening": {"max_screening_age_days": 365, "fuzzy_match_threshold": 0.85},
            "identity": {"min_verified_docs": 1, "doc_expiry_warning_days": 90, "accepted_doc_types": ["passport"]},
            "beneficial_ownership": {"ownership_threshold_pct": 25.0, "max_chain_depth": 4},
            "transactions": {"edd_trigger_threshold_usd": 10000.0, "velocity_window_days": 90},
            "documents": {"max_doc_age_days": 90, "accepted_proof_of_address_types": ["utility_bill"]},
            "data_quality": {"critical_fields": ["customer_id"], "poor_quality_threshold": 0.2},
        }
        engine.evaluate_customer("T001", institution_id=None)
        mock_jur.assert_called_once_with("USA")
        mock_inst.assert_not_called()


# INST-W-002: institution_id non-None uses get_institution_params
def test_inst_w_002_non_none_uses_institution_params():
    engine = _make_engine()
    engine.customers = _minimal_customers("T002")
    engine.screenings = _minimal_screenings("T002")
    engine.id_verifications = pd.DataFrame()
    engine.transactions = pd.DataFrame()
    engine.documents = pd.DataFrame()
    engine.beneficial_owners = pd.DataFrame()

    with patch("kyc_engine.engine.get_institution_params") as mock_inst, \
         patch("kyc_engine.engine.get_jurisdiction_params") as mock_jur:
        mock_inst.return_value = {
            "screening": {"max_screening_age_days": 180, "fuzzy_match_threshold": 0.90},
            "identity": {"min_verified_docs": 2, "doc_expiry_warning_days": 60, "accepted_doc_types": ["passport"]},
            "beneficial_ownership": {"ownership_threshold_pct": 10.0, "max_chain_depth": 4},
            "transactions": {"edd_trigger_threshold_usd": 5000.0, "velocity_window_days": 60},
            "documents": {"max_doc_age_days": 60, "accepted_proof_of_address_types": ["utility_bill"]},
            "data_quality": {"critical_fields": ["customer_id"], "poor_quality_threshold": 0.2},
        }
        engine.evaluate_customer("T002", institution_id="BANK001")
        mock_inst.assert_called_once_with("USA", "BANK001")
        mock_jur.assert_not_called()


# INST-W-003: result still contains expected keys when institution_id supplied
def test_inst_w_003_result_shape_with_institution():
    engine = _make_engine()
    engine.customers = _minimal_customers("T003")
    engine.screenings = _minimal_screenings("T003")
    engine.id_verifications = pd.DataFrame()
    engine.transactions = pd.DataFrame()
    engine.documents = pd.DataFrame()
    engine.beneficial_owners = pd.DataFrame()

    with patch("kyc_engine.engine.get_institution_params") as mock_inst:
        mock_inst.return_value = {
            "screening": {"max_screening_age_days": 365, "fuzzy_match_threshold": 0.85},
            "identity": {"min_verified_docs": 1, "doc_expiry_warning_days": 90, "accepted_doc_types": ["passport"]},
            "beneficial_ownership": {"ownership_threshold_pct": 25.0, "max_chain_depth": 4},
            "transactions": {"edd_trigger_threshold_usd": 10000.0, "velocity_window_days": 90},
            "documents": {"max_doc_age_days": 90, "accepted_proof_of_address_types": ["utility_bill"]},
            "data_quality": {"critical_fields": ["customer_id"], "poor_quality_threshold": 0.2},
        }
        result = engine.evaluate_customer("T003", institution_id="BANK001")

    for key in ("customer_id", "jurisdiction", "overall_score", "disposition",
                "aml_screening_score", "ruleset_version"):
        assert key in result, f"Missing key: {key}"
