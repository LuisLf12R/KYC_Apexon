"""
Engine tests — must run without Streamlit installed.
"""
import pytest
from pathlib import Path
from kyc_engine import KYCComplianceEngine


def make_engine():
    """Engine with empty data dirs — tests synthetic data only."""
    return KYCComplianceEngine(data_clean_dir=Path("/nonexistent"))


def test_engine_imports_without_streamlit():
    engine = make_engine()
    assert engine is not None


def test_confirmed_sanctions_match_is_reject():
    engine = make_engine()
    # Override screening data inline
    import pandas as pd
    from datetime import datetime
    engine.screenings = pd.DataFrame([{
        "customer_id": "T001",
        "screening_date": datetime.now().isoformat(),
        "screening_result": "MATCH",
        "hit_status": "CONFIRMED",
        "match_name": "Test Name",
        "list_reference": "OFAC-SDN",
    }])
    engine.customers = pd.DataFrame([{"customer_id": "T001"}])
    engine.id_verifications = pd.DataFrame()
    engine.transactions = pd.DataFrame()
    engine.beneficial_owners = pd.DataFrame()

    result = engine.evaluate_customer("T001")
    assert result["disposition"] == "REJECT"


def test_no_screening_record_defaults_to_review():
    engine = make_engine()
    import pandas as pd
    engine.screenings = pd.DataFrame()
    engine.customers = pd.DataFrame([{"customer_id": "T002"}])
    engine.id_verifications = pd.DataFrame()
    engine.transactions = pd.DataFrame()
    engine.beneficial_owners = pd.DataFrame()

    result = engine.evaluate_customer("T002")
    assert result["disposition"] == "REVIEW"


def test_ruleset_version_flows_through():
    engine = make_engine()
    import pandas as pd
    engine.screenings = pd.DataFrame()
    engine.customers = pd.DataFrame([{"customer_id": "T003"}])
    engine.id_verifications = pd.DataFrame()
    engine.transactions = pd.DataFrame()
    engine.beneficial_owners = pd.DataFrame()

    result = engine.evaluate_customer("T003")
    assert result["ruleset_version"] == engine.ruleset_version


def test_load_ruleset_returns_dict():
    from kyc_engine.ruleset import load_ruleset, reset_ruleset_cache
    from rules.schema.ruleset import RulesetManifest

    reset_ruleset_cache()
    manifest = load_ruleset()
    assert isinstance(manifest, RulesetManifest)
    assert manifest.version.startswith("kyc-rules-v")
    assert manifest.dimension_parameters is not None
