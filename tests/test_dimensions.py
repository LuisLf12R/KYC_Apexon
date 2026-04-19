def test_screening_empty_dataframe_triggers_hr004():
    import pandas as pd
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.aml_screening import AMLScreeningDimension

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.screening
    dim = AMLScreeningDimension(params)
    result = dim.evaluate("TEST-001", {"screening": pd.DataFrame()})
    findings_text = str(result)
    assert "HR-004" in findings_text


def test_screening_missing_key_triggers_hr004():
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from kyc_engine.dimensions.aml_screening import AMLScreeningDimension

    reset_ruleset_cache()
    params = load_ruleset().dimension_parameters.screening
    dim = AMLScreeningDimension(params)
    result = dim.evaluate("TEST-002", {})
    findings_text = str(result)
    assert "HR-004" in findings_text
