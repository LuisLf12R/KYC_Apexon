"""P8-D: Verify CAN/UAE/IND merged + production release cut."""
import json
from pathlib import Path

import pytest

RULESET_PATH = Path("rules/kyc_rules_v2.0.json")
EXPECTED_JURISDICTIONS = ["CAN", "UAE", "IND"]


class TestMergeAndRelease:
    """P8-D merge and release tests."""

    @pytest.fixture(autouse=True)
    def load_ruleset(self):
        self.raw = json.loads(RULESET_PATH.read_text())
        # Handle both dict and list formats for jurisdiction overrides
        jo = self.raw.get("jurisdiction_overrides", self.raw.get("jurisdictions", {}))
        if isinstance(jo, dict):
            self.jurisdiction_codes = set(jo.keys())
            self.jurisdiction_data = jo
        elif isinstance(jo, list):
            self.jurisdiction_codes = {
                item.get("jurisdiction_code", item.get("code", ""))
                for item in jo
            }
            self.jurisdiction_data = {
                item.get("jurisdiction_code", item.get("code", "")): item
                for item in jo
            }
        else:
            self.jurisdiction_codes = set()
            self.jurisdiction_data = {}

    def test_mr_001_can_merged(self):
        """MR-001: CAN is present in jurisdiction overrides."""
        assert "CAN" in self.jurisdiction_codes

    def test_mr_002_uae_merged(self):
        """MR-002: UAE is present in jurisdiction overrides."""
        assert "UAE" in self.jurisdiction_codes

    def test_mr_003_ind_merged(self):
        """MR-003: IND is present in jurisdiction overrides."""
        assert "IND" in self.jurisdiction_codes

    def test_mr_004_can_has_crs_fatca(self):
        """MR-004: CAN overlay includes crs_fatca dimension_overrides."""
        can = self.jurisdiction_data.get("CAN", {})
        do = can.get("dimension_overrides", {})
        assert "crs_fatca" in do, "CAN missing crs_fatca after merge"

    def test_mr_005_uae_has_crs_fatca(self):
        """MR-005: UAE overlay includes crs_fatca dimension_overrides."""
        uae = self.jurisdiction_data.get("UAE", {})
        do = uae.get("dimension_overrides", {})
        assert "crs_fatca" in do, "UAE missing crs_fatca after merge"

    def test_mr_006_ind_has_crs_fatca(self):
        """MR-006: IND overlay includes crs_fatca dimension_overrides."""
        ind = self.jurisdiction_data.get("IND", {})
        do = ind.get("dimension_overrides", {})
        assert "crs_fatca" in do, "IND missing crs_fatca after merge"

    def test_mr_007_changelog_has_merge_entries(self):
        """MR-007: Changelog contains entries for the merges."""
        cl = self.raw.get("changelog", [])
        reviewed = [e for e in cl if e.get("reviewed_by") == "NYU RegTech Team"]
        assert len(reviewed) >= 3, (
            f"Expected at least 3 reviewed changelog entries, got {len(reviewed)}"
        )

    def test_mr_008_no_null_reviewed_by_after_release(self):
        """MR-008: No null reviewed_by after release (P8-A guarantee holds)."""
        cl = self.raw.get("changelog", [])
        nulls = [e for e in cl if e.get("reviewed_by") is None]
        assert len(nulls) == 0, f"{len(nulls)} null reviewed_by entries remain"
