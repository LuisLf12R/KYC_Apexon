"""
Phase 1 schema tests.
Run with: pytest tests/test_ruleset_schema.py -v
Must pass without Streamlit installed.
"""
import json
import pytest
from pathlib import Path
from pydantic import ValidationError

from rules.schema import RulesetManifest

RULES_DIR = Path(__file__).parent.parent / "rules"
V11_PATH = RULES_DIR / "kyc_rules_v2.0.json"


def load_v11() -> dict:
    return json.loads(V11_PATH.read_text())


class TestRulesetLoads:
    def test_v11_loads_without_error(self):
        data = load_v11()
        manifest = RulesetManifest.model_validate(data)
        assert manifest.version == "kyc-rules-v2.0"

    def test_correct_rule_counts(self):
        manifest = RulesetManifest.model_validate(load_v11())
        assert len(manifest.hard_reject_rules) == 4
        assert len(manifest.review_rules) == 8

    def test_no_duplicate_rule_ids(self):
        manifest = RulesetManifest.model_validate(load_v11())
        ids = [r.rule_id for r in manifest.hard_reject_rules + manifest.review_rules]
        assert len(ids) == len(set(ids))

    def test_score_thresholds_ordered(self):
        manifest = RulesetManifest.model_validate(load_v11())
        assert manifest.score_thresholds.pass_minimum > manifest.score_thresholds.pass_with_notes_minimum

    def test_all_rules_have_provenance(self):
        manifest = RulesetManifest.model_validate(load_v11())
        for rule in manifest.hard_reject_rules + manifest.review_rules:
            assert rule.provenance is not None
            assert len(rule.provenance.regulatory_refs) >= 1

    def test_all_provenances_have_source_url(self):
        manifest = RulesetManifest.model_validate(load_v11())
        for rule in manifest.hard_reject_rules + manifest.review_rules:
            assert str(rule.provenance.source_url).startswith("https://")

    def test_dimension_parameters_present(self):
        manifest = RulesetManifest.model_validate(load_v11())
        dp = manifest.dimension_parameters
        assert dp.identity.min_verified_docs >= 1
        assert 0 < dp.screening.fuzzy_match_threshold <= 1.0
        assert dp.beneficial_ownership.ownership_threshold_pct == 25.0
        assert dp.transactions.edd_trigger_threshold_usd > 0
        assert dp.documents.max_doc_age_days > 0
        assert len(dp.data_quality.critical_fields) >= 1


class TestSchemaValidation:
    def test_rejects_empty_regulatory_refs(self):
        data = load_v11()
        data["hard_reject_rules"][0]["provenance"]["regulatory_refs"] = []
        with pytest.raises(ValidationError):
            RulesetManifest.model_validate(data)

    def test_rejects_inverted_score_thresholds(self):
        data = load_v11()
        data["score_thresholds"]["pass_minimum"] = 40
        data["score_thresholds"]["pass_with_notes_minimum"] = 60
        with pytest.raises(ValidationError):
            RulesetManifest.model_validate(data)

    def test_rejects_bad_snapshot_hash_length(self):
        data = load_v11()
        data["hard_reject_rules"][0]["provenance"]["snapshot_hash"] = "tooshort"
        with pytest.raises(ValidationError):
            RulesetManifest.model_validate(data)

    def test_rejects_duplicate_rule_ids(self):
        data = load_v11()
        dupe = data["hard_reject_rules"][0].copy()
        data["review_rules"].append(dupe)
        with pytest.raises(ValidationError):
            RulesetManifest.model_validate(data)


class TestJurisdictionMergeLogic:
    """Tests for get_jurisdiction_params merge behaviour (P3-2)."""

    def setup_method(self):
        from kyc_engine.ruleset import reset_ruleset_cache
        reset_ruleset_cache()

    def teardown_method(self):
        from kyc_engine.ruleset import reset_ruleset_cache
        reset_ruleset_cache()

    def test_unknown_jurisdiction_returns_baseline(self):
        """Jurisdiction code not in manifest falls back to baseline unchanged."""
        from kyc_engine.ruleset import get_jurisdiction_params, load_ruleset
        baseline_manifest = load_ruleset()
        try:
            baseline = baseline_manifest.dimension_parameters.model_dump()
        except AttributeError:
            baseline = baseline_manifest.dimension_parameters.dict()

        result = get_jurisdiction_params("ZZZ")
        assert result == baseline

    def test_empty_jurisdictions_returns_baseline(self):
        """Manifest with no jurisdictions block returns baseline."""
        from kyc_engine.ruleset import get_jurisdiction_params, load_ruleset
        manifest = load_ruleset()
        # v1.1 has no jurisdictions — this is the live baseline test
        if not manifest.jurisdictions:
            result = get_jurisdiction_params("USA")
            try:
                baseline = manifest.dimension_parameters.model_dump()
            except AttributeError:
                baseline = manifest.dimension_parameters.dict()
            assert result == baseline

    def test_partial_override_preserves_baseline_fields(self, tmp_path, monkeypatch):
        """A jurisdiction that overrides one sub-field leaves others intact."""
        import json
        from kyc_engine import ruleset as ruleset_mod

        # Build a minimal manifest JSON with one jurisdiction override
        manifest_data = {
            "version": "test-v0.1",
            "effective_date": "2026-01-01",
            "created_by": "test",
            "description": "test",
            "changelog": [],
            "disposition_levels": {},
            "hard_reject_rules": [],
            "review_rules": [],
            "score_thresholds": {
                "pass_minimum": 70,
                "pass_with_notes_minimum": 50,
            },
            "dimension_parameters": {
                "identity": {
                    "min_verified_docs": 1,
                    "doc_expiry_warning_days": 90,
                    "accepted_doc_types": ["passport"],
                },
                "screening": {
                    "max_screening_age_days": 365,
                    "fuzzy_match_threshold": 0.85,
                },
                "beneficial_ownership": {
                    "ownership_threshold_pct": 25.0,
                    "max_chain_depth": 4,
                },
                "transactions": {
                    "edd_trigger_threshold_usd": 10000.0,
                    "velocity_window_days": 90,
                },
                "documents": {
                    "max_doc_age_days": 90,
                    "accepted_proof_of_address_types": ["utility_bill"],
                },
                "data_quality": {
                    "critical_fields": ["customer_id"],
                    "poor_quality_threshold": 0.2,
                },
            },
            "jurisdictions": {
                "HKG": {
                    "jurisdiction_code": "HKG",
                    "regulators": ["HKMA", "SFC"],
                    "dimension_overrides": {
                        "beneficial_ownership": {
                            "ownership_threshold_pct": 10.0,
                        },
                    },
                    "additional_hard_reject_rules": [],
                    "additional_review_rules": [],
                },
            },
        }

        manifest_file = tmp_path / "test_manifest.json"
        manifest_file.write_text(json.dumps(manifest_data))

        # Patch the module to load our test manifest
        monkeypatch.setattr(ruleset_mod, "_ruleset_cache", None)

        def patched_load():
            from rules.schema.ruleset import RulesetManifest
            return RulesetManifest.model_validate(manifest_data)

        monkeypatch.setattr(ruleset_mod, "load_ruleset", patched_load)
        monkeypatch.setattr(ruleset_mod, "_ruleset_cache", None)

        result = ruleset_mod.get_jurisdiction_params("HKG")

        # Override applied: HKG gets 10% threshold
        assert result["beneficial_ownership"]["ownership_threshold_pct"] == 10.0
        # Baseline preserved: max_chain_depth untouched
        assert result["beneficial_ownership"]["max_chain_depth"] == 4
        # Unrelated dimension untouched
        assert result["screening"]["max_screening_age_days"] == 365

    def test_hkg_vs_usa_ubo_threshold_differ(self, tmp_path, monkeypatch):
        """HKG 10% and USA 25% produce different thresholds from same baseline."""
        import json
        from kyc_engine import ruleset as ruleset_mod

        manifest_data = {
            "version": "test-v0.1",
            "effective_date": "2026-01-01",
            "created_by": "test",
            "description": "test",
            "changelog": [],
            "disposition_levels": {},
            "hard_reject_rules": [],
            "review_rules": [],
            "score_thresholds": {
                "pass_minimum": 70,
                "pass_with_notes_minimum": 50,
            },
            "dimension_parameters": {
                "identity": {
                    "min_verified_docs": 1,
                    "doc_expiry_warning_days": 90,
                    "accepted_doc_types": ["passport"],
                },
                "screening": {
                    "max_screening_age_days": 365,
                    "fuzzy_match_threshold": 0.85,
                },
                "beneficial_ownership": {
                    "ownership_threshold_pct": 25.0,
                    "max_chain_depth": 4,
                },
                "transactions": {
                    "edd_trigger_threshold_usd": 10000.0,
                    "velocity_window_days": 90,
                },
                "documents": {
                    "max_doc_age_days": 90,
                    "accepted_proof_of_address_types": ["utility_bill"],
                },
                "data_quality": {
                    "critical_fields": ["customer_id"],
                    "poor_quality_threshold": 0.2,
                },
            },
            "jurisdictions": {
                "HKG": {
                    "jurisdiction_code": "HKG",
                    "regulators": ["HKMA", "SFC"],
                    "dimension_overrides": {
                        "beneficial_ownership": {"ownership_threshold_pct": 10.0},
                    },
                    "additional_hard_reject_rules": [],
                    "additional_review_rules": [],
                },
                "USA": {
                    "jurisdiction_code": "USA",
                    "regulators": ["FinCEN", "OFAC", "OCC"],
                    "dimension_overrides": {
                        "beneficial_ownership": {"ownership_threshold_pct": 25.0},
                    },
                    "additional_hard_reject_rules": [],
                    "additional_review_rules": [],
                },
            },
        }

        def patched_load():
            from rules.schema.ruleset import RulesetManifest
            return RulesetManifest.model_validate(manifest_data)

        monkeypatch.setattr(ruleset_mod, "load_ruleset", patched_load)
        monkeypatch.setattr(ruleset_mod, "_ruleset_cache", None)

        hkg_params = ruleset_mod.get_jurisdiction_params("HKG")
        usa_params = ruleset_mod.get_jurisdiction_params("USA")

        assert hkg_params["beneficial_ownership"]["ownership_threshold_pct"] == 10.0
        assert usa_params["beneficial_ownership"]["ownership_threshold_pct"] == 25.0
        assert (
            hkg_params["beneficial_ownership"]["ownership_threshold_pct"]
            != usa_params["beneficial_ownership"]["ownership_threshold_pct"]
        )


class TestV2JurisdictionSchema:
    """Validate that kyc_rules_v2.0.json loads with correct
    jurisdiction structure and key regulatory values. (P3-5)"""

    def setup_method(self):
        from kyc_engine.ruleset import reset_ruleset_cache
        reset_ruleset_cache()

    def teardown_method(self):
        from kyc_engine.ruleset import reset_ruleset_cache
        reset_ruleset_cache()

    def test_v2_loads_with_eight_jurisdictions(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        assert len(m.jurisdictions) == 8
        expected = {"USA", "GBR", "EU", "CHE", "SGP", "HKG", "AUS", "CHN"}
        assert set(m.jurisdictions.keys()) == expected

    def test_hkg_ubo_threshold_is_10_pct(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        hkg = m.jurisdictions["HKG"]
        ubo_override = hkg.dimension_overrides.get("beneficial_ownership", {})
        assert ubo_override.get("ownership_threshold_pct") == 10.0

    def test_sgp_velocity_window_is_30_days(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        sgp = m.jurisdictions["SGP"]
        tx_override = sgp.dimension_overrides.get("transactions", {})
        assert tx_override.get("velocity_window_days") == 30

    def test_eu_rescreening_interval_is_180_days(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        eu = m.jurisdictions["EU"]
        screening_override = eu.dimension_overrides.get("screening", {})
        assert screening_override.get("max_screening_age_days") == 180

    def test_che_velocity_window_is_60_days(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        che = m.jurisdictions["CHE"]
        tx_override = che.dimension_overrides.get("transactions", {})
        assert tx_override.get("velocity_window_days") == 60

    def test_gbr_doc_expiry_warning_is_60_days(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        gbr = m.jurisdictions["GBR"]
        id_override = gbr.dimension_overrides.get("identity", {})
        assert id_override.get("doc_expiry_warning_days") == 60

    def test_baseline_ubo_threshold_is_25_pct(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        try:
            baseline = m.dimension_parameters.model_dump()
        except AttributeError:
            baseline = m.dimension_parameters.dict()
        assert baseline["beneficial_ownership"]["ownership_threshold_pct"] == 25.0

    def test_chn_overlay_has_empty_overrides(self):
        """China placeholder present but no overrides — engine falls back
        to baseline for all params."""
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        chn = m.jurisdictions["CHN"]
        assert chn.dimension_overrides == {}

    def test_disposition_levels_has_all_four(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        assert set(m.disposition_levels.keys()) == {
            "PASS", "PASS_WITH_NOTES", "REVIEW", "REJECT"
        }

    def test_review_requires_human_action(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        assert m.disposition_levels["REVIEW"].requires_human_action is True

    def test_pass_does_not_require_human_action(self):
        from kyc_engine.ruleset import load_ruleset
        m = load_ruleset()
        assert m.disposition_levels["PASS"].requires_human_action is False
