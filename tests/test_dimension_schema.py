from kyc_engine.dimensions.schema import validate_dimension_result


def _minimal_result(overrides=None):
    base = {
        "customer_id": "C001",
        "dimension": "TestDim",
        "passed": True,
        "status": "Compliant",
        "score": 80,
        "findings": ["[PASS] ok"],
        "remediation_required": False,
        "next_review_date": "2027-04-28",
        "evaluation_details": {},
    }
    if overrides:
        base.update(overrides)
    return base


def test_valid_result_passes():
    result = _minimal_result()
    validate_dimension_result(result)  # must not raise


def test_missing_score_raises():
    result = _minimal_result()
    del result["score"]
    try:
        validate_dimension_result(result)
        assert False, "should have raised"
    except KeyError:
        pass


def test_score_out_of_range_raises():
    result = _minimal_result({"score": 150})
    try:
        validate_dimension_result(result)
        assert False, "should have raised"
    except ValueError:
        pass


def test_missing_required_key_raises():
    for key in ("customer_id", "dimension", "passed", "status", "findings",
                "remediation_required", "next_review_date", "evaluation_details"):
        result = _minimal_result()
        del result[key]
        try:
            validate_dimension_result(result)
            assert False, f"should have raised for missing key: {key}"
        except KeyError:
            pass


def test_float_score_raises():
    result = _minimal_result({"score": 80.5})
    try:
        validate_dimension_result(result)
        assert False, "should have raised for float score"
    except ValueError:
        pass


def test_identity_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.identity import IdentityVerificationDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.identity

    customers = pd.DataFrame([{
        "customer_id": "SC001",
        "risk_rating": "LOW",
        "jurisdiction": "US",
        "entity_type": "INDIVIDUAL",
        "customer_name": "Jane Doe",
    }])
    id_verifications = pd.DataFrame([{
        "customer_id": "SC001",
        "document_type": "PASSPORT",
        "expiry_date": "2030-01-01",
        "issue_date": "2020-01-01",
        "verification_date": "2024-01-01",
        "verification_method": "IN_PERSON",
        "name_on_document": "Jane Doe",
    }])
    data = {"customers": customers, "id_verifications": id_verifications}
    dim = IdentityVerificationDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC001", data)

    assert "score" in result, "identity result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)


def test_account_activity_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.account_activity import AccountActivityDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.transactions

    customers = pd.DataFrame([{
        "customer_id": "SC002",
        "risk_rating": "LOW",
        "jurisdiction": "US",
        "entity_type": "INDIVIDUAL",
    }])
    transactions = pd.DataFrame([{
        "customer_id": "SC002",
        "last_txn_date": "2026-03-01",
    }])
    data = {"customers": customers, "transactions": transactions}
    dim = AccountActivityDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC002", data)

    assert "score" in result, "account_activity result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)


def test_proof_of_address_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.proof_of_address import ProofOfAddressDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.documents

    customers = pd.DataFrame([{
        "customer_id": "SC003",
        "risk_rating": "LOW",
        "jurisdiction": "US",
        "entity_type": "INDIVIDUAL",
    }])
    documents = pd.DataFrame([{
        "customer_id": "SC003",
        "document_type": "UTILITY_BILL",
        "issue_date": "2026-02-01",
        "verification_date": "2026-02-01",
    }])
    data = {"customers": customers, "documents": documents}
    dim = ProofOfAddressDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC003", data)

    assert "score" in result, "proof_of_address result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)


def test_data_quality_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.data_quality import DataQualityDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.data_quality

    customers = pd.DataFrame([{
        "customer_id": "SC004",
        "risk_rating": "LOW",
        "entity_type": "INDIVIDUAL",
        "jurisdiction": "US",
        "account_open_date": "2020-01-01",
        "last_kyc_review_date": "2025-01-01",
    }])
    screenings = pd.DataFrame([{
        "customer_id": "SC004",
        "screening_date": "2026-04-27",
        "screening_result": "NO_HIT",
    }])
    empty = pd.DataFrame()
    data = {
        "customers": customers,
        "id_verifications": empty,
        "documents": empty,
        "screenings": screenings,
        "ubo": [],
        "transactions": empty,
    }
    dim = DataQualityDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC004", data)

    assert "score" in result, "data_quality result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    assert result["score"] == round(result["evaluation_details"]["data_quality_score"])
    validate_dimension_result(result)


def test_aml_status_is_in_evaluation_details():
    import pandas as pd
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.aml_screening import AMLScreeningDimension

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.screening
    dim = AMLScreeningDimension(params)

    result = dim.evaluate("TEST-AML", {"screening": pd.DataFrame()})

    assert "aml_status" not in result, "aml_status must be in evaluation_details, not at root"
    assert "aml_hit_status" not in result, "aml_hit_status must be in evaluation_details, not at root"
    assert result.get("evaluation_details", {}).get("aml_status") is not None


def test_engine_adapter_reads_score_directly():
    import inspect
    from kyc_engine import engine as eng_module
    src = inspect.getsource(eng_module)
    assert "_extract_score" not in src, (
        "_extract_score adapter must be removed from engine.py"
    )


def test_beneficial_ownership_result_has_score():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.beneficial_ownership import BeneficialOwnershipDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.beneficial_ownership

    customers = pd.DataFrame([{
        "customer_id": "SC005",
        "risk_rating": "LOW",
        "jurisdiction": "US",
        "entity_type": "INDIVIDUAL",
    }])
    data = {"customers": customers, "ubo": []}
    dim = BeneficialOwnershipDimension(params, evaluation_date=datetime(2026, 4, 28))
    result = dim.evaluate("SC005", data)

    assert "score" in result, "beneficial_ownership result must include 'score'"
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)


def test_aml_result_has_score_and_conforms():
    import pandas as pd
    from datetime import datetime
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.aml_screening import AMLScreeningDimension
    from kyc_engine.dimensions.schema import validate_dimension_result

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.screening
    dim = AMLScreeningDimension(params)

    result = dim.evaluate("TEST-AML2", {"screening": pd.DataFrame()})

    assert "score" in result
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    validate_dimension_result(result)
