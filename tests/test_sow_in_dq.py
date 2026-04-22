"""P8-C: Verify sow_declared is in data_quality critical_fields."""
import json
from pathlib import Path

import pytest

RULESET_PATH = Path("rules/kyc_rules_v2.0.json")


class TestSoWInDQ:
    """P8-C SoW in data_quality critical_fields tests."""

    @pytest.fixture(autouse=True)
    def load_ruleset(self):
        raw = json.loads(RULESET_PATH.read_text())
        self.dq_params = raw.get("dimension_parameters", {}).get("data_quality", {})
        self.critical_fields = self.dq_params.get("critical_fields", [])

    def test_sdq_001_sow_declared_in_critical_fields(self):
        """SDQ-001: sow_declared is present in critical_fields."""
        assert "sow_declared" in self.critical_fields, (
            f"sow_declared not in critical_fields: {self.critical_fields}"
        )

    def test_sdq_002_no_duplicates_in_critical_fields(self):
        """SDQ-002: critical_fields has no duplicate entries."""
        assert len(self.critical_fields) == len(set(self.critical_fields)), (
            f"Duplicates found in critical_fields: {self.critical_fields}"
        )

    def test_sdq_003_critical_fields_all_strings(self):
        """SDQ-003: Every entry in critical_fields is a non-empty string."""
        for field in self.critical_fields:
            assert isinstance(field, str) and len(field.strip()) > 0, (
                f"Invalid critical_field entry: {field!r}"
            )
