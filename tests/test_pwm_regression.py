import datetime as dt

import pandas as pd
import pytest

from kyc_engine.dimensions.account_activity import AccountActivityDimension
from kyc_engine.dimensions.aml_screening import AMLScreeningDimension
from kyc_engine.dimensions.beneficial_ownership import BeneficialOwnershipDimension
from kyc_engine.dimensions.data_quality import DataQualityDimension
from kyc_engine.dimensions.identity import IdentityVerificationDimension
from kyc_engine.dimensions.proof_of_address import ProofOfAddressDimension
from kyc_engine.engine import KYCComplianceEngine


@pytest.fixture
def manifest():
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache

    reset_ruleset_cache()
    return load_ruleset()


@pytest.fixture
def today_str():
    return dt.date.today().isoformat()


def _score_from_result(result: dict) -> float:
    if "score" in result:
        return float(result["score"])
    details = result.get("evaluation_details", {})
    if "data_quality_score" in details:
        return float(details["data_quality_score"])
    if "compliance_score" in details:
        return float(details["compliance_score"])
    if "passed" in result:
        return 100.0 if result["passed"] else 0.0
    raise AssertionError(f"No score-like key found in result: {result}")


# Tier 1 (12 tests)
def test_pwm_t1_001_aml_no_hits_score_gt_50(manifest, today_str):
    dim = AMLScreeningDimension(manifest.dimension_parameters.screening)
    data = {
        "customers": pd.DataFrame([{"customer_id": "C1", "risk_rating": "MEDIUM", "jurisdiction": "US"}]),
        "screenings": pd.DataFrame(
            [{"customer_id": "C1", "screening_date": today_str, "screening_result": "NO_HIT", "list_reference": "OFAC"}]
        ),
        "screening": pd.DataFrame([{"customer_id": "C1"}]),
    }
    result = dim.evaluate("C1", data)
    assert _score_from_result(result) > 50


def test_pwm_t1_002_aml_confirmed_match_reject_level(manifest, today_str):
    dim = AMLScreeningDimension(manifest.dimension_parameters.screening)
    data = {
        "customers": pd.DataFrame([{"customer_id": "C2", "risk_rating": "MEDIUM", "jurisdiction": "US"}]),
        "screenings": pd.DataFrame(
            [{
                "customer_id": "C2",
                "screening_date": today_str,
                "screening_result": "EXACT_MATCH",
                "resolution_status": "RESOLVED_BLOCKED",
                "list_reference": "OFAC",
            }]
        ),
        "screening": pd.DataFrame([{"customer_id": "C2"}]),
    }
    result = dim.evaluate("C2", data)
    text = str(result).lower()
    assert (_score_from_result(result) == 0) or ("confirmed" in text or "non_compliant_blocked_relationship" in text)


def test_pwm_t1_003_aml_missing_key_hr004(manifest):
    dim = AMLScreeningDimension(manifest.dimension_parameters.screening)
    result = dim.evaluate("C3", {})
    assert "HR-004" in str(result)


def test_pwm_t1_004_identity_verified_doc_score_gt_50(manifest, today_str):
    dim = IdentityVerificationDimension(manifest.dimension_parameters.identity)
    data = {
        "customers": pd.DataFrame([{"customer_id": "C4", "risk_rating": "LOW", "jurisdiction": "US", "customer_name": "Alice"}]),
        "id_verifications": pd.DataFrame(
            [{
                "customer_id": "C4",
                "document_type": "PASSPORT",
                "expiry_date": "2099-01-01",
                "issue_date": today_str,
                "verification_date": today_str,
                "verification_method": "manual",
                "name_on_document": "Alice",
            }]
        ),
    }
    result = dim.evaluate("C4", data)
    assert _score_from_result(result) > 50


def test_pwm_t1_005_identity_no_documents_score_le_40(manifest):
    dim = IdentityVerificationDimension(manifest.dimension_parameters.identity)
    data = {
        "customers": pd.DataFrame([{"customer_id": "C5", "risk_rating": "LOW", "jurisdiction": "US"}]),
        "id_verifications": pd.DataFrame(),
    }
    result = dim.evaluate("C5", data)
    assert _score_from_result(result) <= 40


def test_pwm_t1_006_ubo_single_identified_no_reject(manifest, today_str):
    dim = BeneficialOwnershipDimension(manifest.dimension_parameters.beneficial_ownership)
    data = {
        "customers": pd.DataFrame([{"customer_id": "C6", "entity_type": "LEGAL_ENTITY", "jurisdiction": "US", "risk_rating": "LOW"}]),
        "ubo": pd.DataFrame(
            [{
                "customer_id": "C6",
                "ubo_name": "Owner One",
                "ubo_dob": "1990-01-01",
                "ubo_nationality": "US",
                "ownership_percent": 100,
                "verification_date": today_str,
            }]
        ),
        "screenings": pd.DataFrame([{"match_name": "Owner One"}]),
    }
    result = dim.evaluate("C6", data)
    assert "NON_COMPLIANT" not in str(result)


def test_pwm_t1_007_ubo_no_data_score_le_40(manifest):
    dim = BeneficialOwnershipDimension(manifest.dimension_parameters.beneficial_ownership)
    data = {
        "customers": pd.DataFrame([{"customer_id": "C7", "entity_type": "LEGAL_ENTITY", "jurisdiction": "US", "risk_rating": "LOW"}]),
        "ubo": pd.DataFrame(),
        "screenings": pd.DataFrame(),
    }
    result = dim.evaluate("C7", data)
    assert _score_from_result(result) <= 40


def test_pwm_t1_008_account_activity_normal_score_gt_50(manifest, today_str):
    dim = AccountActivityDimension(manifest.dimension_parameters.transactions)
    tx_rows = [{"customer_id": "C8", "last_txn_date": today_str} for _ in range(25)]
    data = {
        "customers": pd.DataFrame([{"customer_id": "C8", "risk_rating": "MEDIUM", "jurisdiction": "US"}]),
        "transactions": pd.DataFrame(tx_rows),
    }
    result = dim.evaluate("C8", data)
    assert _score_from_result(result) > 50


def test_pwm_t1_009_data_quality_all_critical_present_score_gt_60(manifest, today_str):
    dim = DataQualityDimension(manifest.dimension_parameters.data_quality)
    customers = pd.DataFrame([{
        "customer_id": "C9",
        "entity_type": "INDIVIDUAL",
        "jurisdiction": "US",
        "risk_rating": "LOW",
        "account_open_date": today_str,
        "last_kyc_review_date": today_str,
        "country_of_origin": "US",
    }])
    data = {
        "customers": customers,
        "id_verifications": pd.DataFrame([{"customer_id": "C9", "issue_date": today_str, "expiry_date": "2099-01-01", "verification_date": today_str}]),
        "documents": pd.DataFrame([{"customer_id": "C9", "document_category": "POA", "issue_date": today_str, "document_type": "UTILITY_BILL"}]),
        "screenings": pd.DataFrame([{"customer_id": "C9", "screening_date": today_str, "screening_result": "NO_HIT"}]),
        "ubo": pd.DataFrame(),
        "transactions": pd.DataFrame([{"customer_id": "C9", "transaction_date": today_str, "last_txn_date": today_str}]),
    }
    result = dim.evaluate("C9", data)
    assert _score_from_result(result) > 60


def test_pwm_t1_010_data_quality_missing_critical_score_lt_60(manifest):
    dim = DataQualityDimension(manifest.dimension_parameters.data_quality)
    customers = pd.DataFrame([{"customer_id": "C10"}])
    data = {
        "customers": customers,
        "id_verifications": pd.DataFrame(),
        "documents": pd.DataFrame(),
        "screenings": pd.DataFrame(),
        "ubo": pd.DataFrame(),
        "transactions": pd.DataFrame(),
    }
    result = dim.evaluate("C10", data)
    assert _score_from_result(result) < 60


def test_pwm_t1_011_proof_of_address_present_score_gt_50(manifest, today_str):
    dim = ProofOfAddressDimension(manifest.dimension_parameters.documents)
    data = {
        "customers": pd.DataFrame([{"customer_id": "C11", "entity_type": "INDIVIDUAL", "jurisdiction": "US", "risk_rating": "LOW"}]),
        "documents": pd.DataFrame([{
            "customer_id": "C11",
            "document_category": "POA",
            "document_type": "UTILITY_BILL",
            "issue_date": today_str,
            "verification_date": today_str,
        }]),
    }
    result = dim.evaluate("C11", data)
    assert _score_from_result(result) > 50


def test_pwm_t1_012_proof_of_address_absent_score_le_50(manifest):
    dim = ProofOfAddressDimension(manifest.dimension_parameters.documents)
    data = {
        "customers": pd.DataFrame([{"customer_id": "C12", "entity_type": "INDIVIDUAL", "jurisdiction": "US", "risk_rating": "LOW"}]),
        "documents": pd.DataFrame(),
    }
    result = dim.evaluate("C12", data)
    assert _score_from_result(result) <= 50


# Tier 2 (2 tests)
def _write_minimal_csv_fixtures(tmp_path, customer_id: str, today_str: str, confirmed_match: bool):
    customers = pd.DataFrame([{
        "customer_id": customer_id,
        "entity_type": "INDIVIDUAL",
        "jurisdiction": "US",
        "risk_rating": "LOW",
        "account_open_date": today_str,
        "last_kyc_review_date": today_str,
        "country_of_origin": "US",
        "customer_name": "Test User",
    }])
    screenings = pd.DataFrame([{
        "customer_id": customer_id,
        "screening_date": today_str,
        "screening_result": "MATCH" if confirmed_match else "NO_MATCH",
        "hit_status": "CONFIRMED" if confirmed_match else "FALSE_POSITIVE",
        "resolution_status": "RESOLVED_BLOCKED" if confirmed_match else "FALSE_POSITIVE",
        "list_reference": "OFAC",
        "match_name": "Test User",
    }])
    idv = pd.DataFrame([{
        "customer_id": customer_id,
        "document_type": "PASSPORT",
        "issue_date": today_str,
        "expiry_date": "2099-01-01",
        "verification_date": today_str,
        "verification_method": "manual",
        "name_on_document": "Test User",
    }])
    tx = pd.DataFrame([{"customer_id": customer_id, "last_txn_date": today_str, "transaction_date": today_str}])
    docs = pd.DataFrame([{"customer_id": customer_id, "document_category": "POA", "document_type": "UTILITY_BILL", "issue_date": today_str, "verification_date": today_str}])
    ubo = pd.DataFrame(columns=["customer_id", "ubo_name", "ownership_percent"])

    customers.to_csv(tmp_path / "customers_clean.csv", index=False)
    screenings.to_csv(tmp_path / "screenings_clean.csv", index=False)
    idv.to_csv(tmp_path / "id_verifications_clean.csv", index=False)
    tx.to_csv(tmp_path / "transactions_clean.csv", index=False)
    docs.to_csv(tmp_path / "documents_clean.csv", index=False)
    ubo.to_csv(tmp_path / "beneficial_ownership_clean.csv", index=False)


def test_pwm_i_001_integration_clean_not_reject(tmp_path):
    customer_id = "TEST-PWM-I-001"
    today_str = dt.date.today().isoformat()
    _write_minimal_csv_fixtures(tmp_path, customer_id, today_str, confirmed_match=False)
    engine = KYCComplianceEngine(data_clean_dir=tmp_path)
    result = engine.evaluate_customer(customer_id)
    assert result["disposition"] != "REJECT", f"Got: {result['disposition']}"


def test_pwm_i_002_integration_sanctions_reject(tmp_path):
    customer_id = "TEST-PWM-I-002"
    today_str = dt.date.today().isoformat()
    _write_minimal_csv_fixtures(tmp_path, customer_id, today_str, confirmed_match=True)
    engine = KYCComplianceEngine(data_clean_dir=tmp_path)
    result = engine.evaluate_customer(customer_id)
    assert result["disposition"] == "REJECT", f"Got: {result['disposition']}"
