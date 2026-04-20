"""
Extractor core tests (EX-001 through EX-012).

All LLM and HTTP calls are mocked — no network required.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from sources.schema.registry import (
    FetchMethod, ParseMode, RegistryEntry, RegistryManifest, UrlEntry,
)
from sources.schema.fetch_state import FetchStateManifest, UrlState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_url(label="landing", fetch_method=FetchMethod.http_get):
    return UrlEntry(label=label, url="https://example.com/doc", fetch_method=fetch_method)


def _make_source(
    id="TEST-SRC",
    jurisdiction="TST",
    parse_mode=ParseMode.llm,
    active=True,
    fetch_method=FetchMethod.http_get,
):
    return RegistryEntry(
        id=id,
        jurisdiction=jurisdiction,
        regulator="TestReg",
        document_name="Test Document",
        urls=[_make_url(fetch_method=fetch_method)],
        parse_mode=parse_mode,
        relevant_sections="All",
        active=active,
    )


def _make_fetch_state(source_id="TEST-SRC", url_label="landing", status="changed"):
    url_state = UrlState(last_status=status)
    return FetchStateManifest(
        schema_version="1.0",
        generated_at="2026-01-01T00:00:00",
        states={source_id: {url_label: url_state}},
    )


def _make_registry(*sources):
    return RegistryManifest(schema_version="1.0", sources=list(sources))


_VALID_OVERLAY_DICT = {
    "jurisdiction_code": "TST",
    "regulators": ["TestReg"],
    "dimension_overrides": {},
    "additional_hard_reject_rules": [],
    "additional_review_rules": [],
}


# ---------------------------------------------------------------------------
# EX-001: find_changed_sources — basic happy path
# ---------------------------------------------------------------------------

def test_find_changed_sources_returns_changed_llm_source():
    """EX-001: changed llm source is returned."""
    from sources.extractor import find_changed_sources
    src = _make_source()
    registry = _make_registry(src)
    fetch_state = _make_fetch_state(status="changed")
    result = find_changed_sources(registry, fetch_state)
    assert len(result) == 1
    assert result[0].id == "TEST-SRC"


# ---------------------------------------------------------------------------
# EX-002: find_changed_sources — direct parse_mode excluded
# ---------------------------------------------------------------------------

def test_find_changed_sources_excludes_direct_sources():
    """EX-002: direct parse_mode sources are skipped even if status=changed."""
    from sources.extractor import find_changed_sources
    src = _make_source(parse_mode=ParseMode.direct)
    registry = _make_registry(src)
    fetch_state = _make_fetch_state(status="changed")
    result = find_changed_sources(registry, fetch_state)
    assert result == []


# ---------------------------------------------------------------------------
# EX-003: find_changed_sources — api_status (none parse_mode) excluded
# ---------------------------------------------------------------------------

def test_find_changed_sources_excludes_api_status_sources():
    """EX-003: parse_mode=none (api_status) sources are skipped."""
    from sources.extractor import find_changed_sources
    src = _make_source(parse_mode=ParseMode.none, fetch_method=FetchMethod.api_status)
    registry = _make_registry(src)
    fetch_state = _make_fetch_state(status="changed")
    result = find_changed_sources(registry, fetch_state)
    assert result == []


# ---------------------------------------------------------------------------
# EX-004: find_changed_sources — inactive source excluded
# ---------------------------------------------------------------------------

def test_find_changed_sources_excludes_inactive_sources():
    """EX-004: active=False sources are skipped."""
    from sources.extractor import find_changed_sources
    src = _make_source(active=False)
    registry = _make_registry(src)
    fetch_state = _make_fetch_state(status="changed")
    result = find_changed_sources(registry, fetch_state)
    assert result == []


# ---------------------------------------------------------------------------
# EX-005: find_changed_sources — ok/null status excluded
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["ok", "error", None])
def test_find_changed_sources_excludes_non_changed_status(status):
    """EX-005: sources with status ok, error, or null are excluded."""
    from sources.extractor import find_changed_sources
    src = _make_source()
    registry = _make_registry(src)
    fetch_state = _make_fetch_state(status=status)
    result = find_changed_sources(registry, fetch_state)
    assert result == []


# ---------------------------------------------------------------------------
# EX-006: validate_overlay — accepts valid dict
# ---------------------------------------------------------------------------

def test_validate_overlay_accepts_valid_dict():
    """EX-006: valid overlay dict passes schema validation."""
    from sources.extractor.extractor import validate_overlay
    overlay = validate_overlay(_VALID_OVERLAY_DICT)
    assert overlay.jurisdiction_code == "TST"
    assert overlay.regulators == ["TestReg"]


# ---------------------------------------------------------------------------
# EX-007: validate_overlay — rejects missing jurisdiction_code
# ---------------------------------------------------------------------------

def test_validate_overlay_rejects_missing_jurisdiction_code():
    """EX-007: overlay dict without jurisdiction_code raises ValidationError."""
    from pydantic import ValidationError
    from sources.extractor.extractor import validate_overlay
    bad = {k: v for k, v in _VALID_OVERLAY_DICT.items() if k != "jurisdiction_code"}
    with pytest.raises(ValidationError):
        validate_overlay(bad)


# ---------------------------------------------------------------------------
# EX-008: validate_overlay — rejects empty regulators
# ---------------------------------------------------------------------------

def test_validate_overlay_rejects_empty_regulators():
    """EX-008: overlay dict with empty regulators list raises ValidationError."""
    from pydantic import ValidationError
    from sources.extractor.extractor import validate_overlay
    bad = {**_VALID_OVERLAY_DICT, "regulators": []}
    with pytest.raises(ValidationError):
        validate_overlay(bad)


# ---------------------------------------------------------------------------
# EX-009: write_staging — writes valid JSON file
# ---------------------------------------------------------------------------

def test_write_staging_writes_json_file(tmp_path, monkeypatch):
    """EX-009: write_staging creates a valid JSON file in the staging dir."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from rules.schema import JurisdictionOverlay
    from sources.extractor.staging import write_staging

    overlay = JurisdictionOverlay.model_validate(_VALID_OVERLAY_DICT)
    path = write_staging(overlay)

    assert path.exists()
    data = json.loads(path.read_text())
    assert data["jurisdiction_code"] == "TST"


# ---------------------------------------------------------------------------
# EX-010: write_staging — filename matches jurisdiction_code
# ---------------------------------------------------------------------------

def test_write_staging_filename_matches_jurisdiction_code(tmp_path, monkeypatch):
    """EX-010: staged file is named <jurisdiction_code>.json."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from rules.schema import JurisdictionOverlay
    from sources.extractor.staging import write_staging

    overlay = JurisdictionOverlay.model_validate(_VALID_OVERLAY_DICT)
    path = write_staging(overlay)
    assert path.name == "TST.json"


# ---------------------------------------------------------------------------
# EX-011: read_staging — loads and validates staged overlay
# ---------------------------------------------------------------------------

def test_read_staging_loads_and_validates(tmp_path, monkeypatch):
    """EX-011: read_staging returns a valid JurisdictionOverlay."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from rules.schema import JurisdictionOverlay
    from sources.extractor.staging import write_staging, read_staging

    overlay = JurisdictionOverlay.model_validate(_VALID_OVERLAY_DICT)
    write_staging(overlay)

    loaded = read_staging("TST")
    assert isinstance(loaded, JurisdictionOverlay)
    assert loaded.jurisdiction_code == "TST"


# ---------------------------------------------------------------------------
# EX-012: build_prompt — includes source metadata
# ---------------------------------------------------------------------------

def test_build_prompt_includes_source_metadata():
    """EX-012: prompt contains source id, jurisdiction, and regulator."""
    from sources.extractor.extractor import build_prompt
    src = _make_source(id="FINTRAC-PCMLTFA", jurisdiction="CAN")
    prompt = build_prompt(src, "sample regulatory text")
    assert "FINTRAC-PCMLTFA" in prompt
    assert "CAN" in prompt
    assert "sample regulatory text" in prompt
