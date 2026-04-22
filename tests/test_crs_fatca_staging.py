"""P8-B: Verify CRS/FATCA dimension_overrides in CAN/UAE/IND staging overlays."""
import json
from pathlib import Path

import pytest

from rules.schema import JurisdictionOverlay

STAGING_DIR = Path("rules/staging")
EXPECTED_JURISDICTIONS = ["CAN", "UAE", "IND"]
REQUIRED_KEYS = [
    "fatca_applicable_jurisdictions",
    "crs_participating_jurisdictions",
    "w8_w9_required_entity_types",
]


class TestCRSFATCAStaging:
    """P8-B CRS/FATCA staging overlay tests."""

    @pytest.fixture(params=EXPECTED_JURISDICTIONS)
    def overlay(self, request):
        code = request.param
        path = STAGING_DIR / f"{code}.json"
        assert path.exists(), f"Staging overlay not found: {path}"
        data = json.loads(path.read_text())

        # Schema round-trip validation for each overlay
        validated = JurisdictionOverlay.model_validate(data)
        data = validated.model_dump(mode="json")
        return code, data

    def test_cfs_001_crs_fatca_section_exists(self, overlay):
        """CFS-001: dimension_overrides contains a crs_fatca section."""
        code, data = overlay
        do = data.get("dimension_overrides", {})
        assert "crs_fatca" in do, (
            f"{code} staging overlay missing crs_fatca in dimension_overrides"
        )

    def test_cfs_002_required_keys_present(self, overlay):
        """CFS-002: crs_fatca section contains all required parameter keys."""
        code, data = overlay
        crs_fatca = data["dimension_overrides"]["crs_fatca"]
        for key in REQUIRED_KEYS:
            assert key in crs_fatca, (
                f"{code}: crs_fatca missing required key '{key}'"
            )

    def test_cfs_003_jurisdiction_in_own_lists(self, overlay):
        """CFS-003: Each jurisdiction includes itself in its FATCA and CRS lists."""
        code, data = overlay
        crs_fatca = data["dimension_overrides"]["crs_fatca"]
        assert code in crs_fatca["fatca_applicable_jurisdictions"], (
            f"{code} not in its own fatca_applicable_jurisdictions"
        )
        assert code in crs_fatca["crs_participating_jurisdictions"], (
            f"{code} not in its own crs_participating_jurisdictions"
        )

    def test_cfs_004_entity_types_non_empty(self, overlay):
        """CFS-004: w8_w9_required_entity_types is a non-empty list."""
        code, data = overlay
        types = data["dimension_overrides"]["crs_fatca"]["w8_w9_required_entity_types"]
        assert isinstance(types, list) and len(types) > 0, (
            f"{code}: w8_w9_required_entity_types must be a non-empty list"
        )

    def test_cfs_005_uae_includes_foundation(self, overlay):
        """CFS-005: UAE entity types include 'foundation' (DIFC/ADGM structure)."""
        code, data = overlay
        if code != "UAE":
            pytest.skip("UAE-specific test")
        types = data["dimension_overrides"]["crs_fatca"]["w8_w9_required_entity_types"]
        assert "foundation" in types, (
            "UAE w8_w9_required_entity_types should include 'foundation'"
        )
