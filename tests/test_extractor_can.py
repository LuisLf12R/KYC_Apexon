"""
CAN overlay extraction pipeline tests (CAN-001 through CAN-005).

All HTTP and LLM calls are mocked. No network required.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from sources.schema.registry import (
    FetchMethod, ParseMode, RegistryEntry, RegistryManifest, UrlEntry,
)
from sources.schema.fetch_state import FetchStateManifest, UrlState


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_CAN_OVERLAY_RESPONSE = json.dumps({
    "jurisdiction_code": "CAN",
    "regulators": ["FINTRAC"],
    "dimension_overrides": {
        "beneficial_ownership": {
            "ownership_threshold_pct": 25.0
        },
        "transactions": {
            "edd_trigger_threshold_usd": 10000.0,
            "velocity_window_days": 90
        }
    },
    "additional_hard_reject_rules": [],
    "additional_review_rules": [],
})


@pytest.fixture()
def fintrac_source():
    """Real-structure FINTRAC-PCMLTFA RegistryEntry (metadata from registry.yaml)."""
    return RegistryEntry(
        id="FINTRAC-PCMLTFA",
        jurisdiction="CAN",
        regulator="FINTRAC",
        document_name="Proceeds of Crime (Money Laundering) and Terrorist Financing Act",
        urls=[
            UrlEntry(
                label="landing",
                url="https://laws-lois.justice.gc.ca/eng/acts/P-24.501/",
                fetch_method=FetchMethod.http_get,
            )
        ],
        parse_mode=ParseMode.llm,
        relevant_sections="Part 1 customer identification, beneficial ownership, record keeping",
        active=True,
    )


@pytest.fixture()
def can_fetch_state():
    """FetchStateManifest with FINTRAC-PCMLTFA landing URL in changed state."""
    return FetchStateManifest(
        schema_version="1.0",
        generated_at="2026-01-01T00:00:00",
        states={
            "FINTRAC-PCMLTFA": {
                "landing": UrlState(last_status="changed")
            }
        },
    )


# ---------------------------------------------------------------------------
# CAN-001: FINTRAC-PCMLTFA is found by find_changed_sources
# ---------------------------------------------------------------------------

def test_can_001_fintrac_found_in_changed_sources(fintrac_source, can_fetch_state):
    """CAN-001: FINTRAC-PCMLTFA with status=changed is returned by find_changed_sources."""
    from sources.extractor import find_changed_sources
    registry = RegistryManifest(schema_version="1.0", sources=[fintrac_source])
    result = find_changed_sources(registry, can_fetch_state)
    assert len(result) == 1
    assert result[0].id == "FINTRAC-PCMLTFA"
    assert result[0].jurisdiction == "CAN"


# ---------------------------------------------------------------------------
# CAN-002: extract_source produces valid CAN JurisdictionOverlay
# ---------------------------------------------------------------------------

def test_can_002_extract_source_produces_valid_can_overlay(
    fintrac_source, tmp_path, monkeypatch
):
    """CAN-002: extract_source with mocked content+LLM returns valid CAN overlay."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from sources.extractor import extract_source

    overlay = extract_source(
        fintrac_source,
        _fetch_content_fn=lambda src: "FINTRAC regulatory text content",
        _call_llm_fn=lambda prompt: _CAN_OVERLAY_RESPONSE,
    )

    assert overlay.jurisdiction_code == "CAN"
    assert "FINTRAC" in overlay.regulators


# ---------------------------------------------------------------------------
# CAN-003: extract_source writes CAN.json to staging
# ---------------------------------------------------------------------------

def test_can_003_extract_source_writes_staging_file(
    fintrac_source, tmp_path, monkeypatch
):
    """CAN-003: after extract_source, rules/staging/CAN.json exists and is valid JSON."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from sources.extractor import extract_source

    extract_source(
        fintrac_source,
        _fetch_content_fn=lambda src: "FINTRAC regulatory text content",
        _call_llm_fn=lambda prompt: _CAN_OVERLAY_RESPONSE,
    )

    staged_file = tmp_path / "CAN.json"
    assert staged_file.exists(), "CAN.json not found in staging dir"
    data = json.loads(staged_file.read_text())
    assert data["jurisdiction_code"] == "CAN"


# ---------------------------------------------------------------------------
# CAN-004: staged CAN overlay passes JurisdictionOverlay schema validation
# ---------------------------------------------------------------------------

def test_can_004_staged_can_overlay_passes_schema(
    fintrac_source, tmp_path, monkeypatch
):
    """CAN-004: staged CAN.json round-trips through JurisdictionOverlay.model_validate."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from sources.extractor import extract_source
    from sources.extractor.staging import read_staging
    from rules.schema import JurisdictionOverlay

    extract_source(
        fintrac_source,
        _fetch_content_fn=lambda src: "FINTRAC regulatory text content",
        _call_llm_fn=lambda prompt: _CAN_OVERLAY_RESPONSE,
    )

    loaded = read_staging("CAN")
    assert isinstance(loaded, JurisdictionOverlay)
    assert loaded.jurisdiction_code == "CAN"
    assert isinstance(loaded.dimension_overrides, dict)


# ---------------------------------------------------------------------------
# CAN-005: run_extraction end-to-end returns CAN overlay
# ---------------------------------------------------------------------------

def test_can_005_run_extraction_returns_can_overlay(
    fintrac_source, can_fetch_state, tmp_path, monkeypatch
):
    """CAN-005: run_extraction with FINTRAC in changed state returns one CAN overlay."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from sources.extractor import run_extraction

    registry = RegistryManifest(schema_version="1.0", sources=[fintrac_source])

    results = run_extraction(
        registry=registry,
        fetch_state=can_fetch_state,
        _fetch_content_fn=lambda src: "FINTRAC regulatory text content",
        _call_llm_fn=lambda prompt: _CAN_OVERLAY_RESPONSE,
    )

    assert len(results) == 1
    assert results[0].jurisdiction_code == "CAN"
