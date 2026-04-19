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
V11_PATH = RULES_DIR / "kyc_rules_v1.1.json"


def load_v11() -> dict:
    return json.loads(V11_PATH.read_text())


class TestRulesetLoads:
    def test_v11_loads_without_error(self):
        data = load_v11()
        manifest = RulesetManifest.model_validate(data)
        assert manifest.version == "kyc-rules-v1.1"

    def test_correct_rule_counts(self):
        manifest = RulesetManifest.model_validate(load_v11())
        assert len(manifest.hard_reject_rules) == 4
        assert len(manifest.review_rules) == 6

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
