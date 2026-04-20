"""
P4-2 — Registry schema tests.

Coverage:
  RS-001  Full registry.yaml loads and validates without error
  RS-002  Source count matches expected total (30)
  RS-003  Only PBOC-AML is active=False
  RS-004  All api_status sources have parse_mode=none
  RS-005  No non-api_status source has parse_mode=none
  RS-006  Invalid fetch_method raises ValidationError
  RS-007  Invalid parse_mode raises ValidationError
  RS-008  api_status URL with non-none parse_mode raises ValidationError
  RS-009  non-api_status URL with parse_mode=none raises ValidationError
  RS-010  Duplicate source ids raises ValidationError
  RS-011  notes=null is valid (optional field)
"""

import pytest
from pydantic import ValidationError

from sources.schema.registry import (
    FetchMethod,
    ParseMode,
    RegistryEntry,
    RegistryManifest,
    UrlEntry,
    load_registry,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _minimal_http_entry(**overrides) -> dict:
    base = {
        "id": "TEST-SRC",
        "jurisdiction": "TEST",
        "regulator": "TestReg",
        "document_name": "Test Document",
        "urls": [{"label": "main", "url": "https://example.com/doc", "fetch_method": "http_get"}],
        "parse_mode": "llm",
        "relevant_sections": "Section 1",
        "active": True,
        "notes": None,
    }
    base.update(overrides)
    return base


def _minimal_api_entry(**overrides) -> dict:
    base = {
        "id": "TEST-API",
        "jurisdiction": "TEST",
        "regulator": "TestReg",
        "document_name": "Test API",
        "urls": [{"label": "api", "url": "https://api.example.com/health", "fetch_method": "api_status"}],
        "parse_mode": "none",
        "relevant_sections": "N/A",
        "active": True,
        "notes": None,
    }
    base.update(overrides)
    return base


# ── RS-001: full registry loads ───────────────────────────────────────────────

class TestRegistryLoads:
    def test_rs_001_registry_yaml_loads_without_error(self):
        manifest = load_registry()
        assert isinstance(manifest, RegistryManifest)
        assert manifest.schema_version == "1.0"

    def test_rs_002_source_count(self):
        manifest = load_registry()
        assert len(manifest.sources) == 30

    def test_rs_003_only_pboc_is_inactive(self):
        manifest = load_registry()
        inactive = [s.id for s in manifest.sources if not s.active]
        assert inactive == ["PBOC-AML"]

    def test_rs_004_api_status_sources_have_parse_mode_none(self):
        manifest = load_registry()
        for source in manifest.sources:
            all_api = all(u.fetch_method == FetchMethod.api_status for u in source.urls)
            if all_api:
                assert source.parse_mode == ParseMode.none, (
                    f"{source.id}: all urls are api_status but parse_mode={source.parse_mode}"
                )

    def test_rs_005_non_api_sources_do_not_have_parse_mode_none(self):
        manifest = load_registry()
        for source in manifest.sources:
            all_api = all(u.fetch_method == FetchMethod.api_status for u in source.urls)
            if not all_api:
                assert source.parse_mode != ParseMode.none, (
                    f"{source.id}: has non-api_status url but parse_mode=none"
                )


# ── RS-006 to RS-011: validation enforcement ──────────────────────────────────

class TestRegistryValidation:
    def test_rs_006_invalid_fetch_method_raises(self):
        data = _minimal_http_entry()
        data["urls"][0]["fetch_method"] = "scrape"  # not a valid FetchMethod
        with pytest.raises(ValidationError) as exc_info:
            RegistryEntry.model_validate(data)
        assert "fetch_method" in str(exc_info.value).lower() or "scrape" in str(exc_info.value)

    def test_rs_007_invalid_parse_mode_raises(self):
        data = _minimal_http_entry(parse_mode="ai")  # not a valid ParseMode
        with pytest.raises(ValidationError) as exc_info:
            RegistryEntry.model_validate(data)
        assert "parse_mode" in str(exc_info.value).lower() or "ai" in str(exc_info.value)

    def test_rs_008_api_status_with_non_none_parse_mode_raises(self):
        data = _minimal_api_entry(parse_mode="llm")
        with pytest.raises(ValidationError) as exc_info:
            RegistryEntry.model_validate(data)
        assert "api_status" in str(exc_info.value) or "none" in str(exc_info.value)

    def test_rs_009_non_api_with_parse_mode_none_raises(self):
        data = _minimal_http_entry(parse_mode="none")
        with pytest.raises(ValidationError) as exc_info:
            RegistryEntry.model_validate(data)
        assert "none" in str(exc_info.value)

    def test_rs_010_duplicate_source_ids_raises(self):
        entry = _minimal_http_entry()
        manifest_data = {
            "schema_version": "1.0",
            "sources": [entry, entry],  # same id twice
        }
        with pytest.raises(ValidationError) as exc_info:
            RegistryManifest.model_validate(manifest_data)
        assert "duplicate" in str(exc_info.value).lower()

    def test_rs_011_notes_null_is_valid(self):
        data = _minimal_http_entry(notes=None)
        entry = RegistryEntry.model_validate(data)
        assert entry.notes is None
