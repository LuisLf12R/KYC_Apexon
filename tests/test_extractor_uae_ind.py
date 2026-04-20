"""
UAE and IND overlay extraction pipeline tests (UAE-001 through UAE-003, IND-001 through IND-003).

All HTTP and LLM calls are mocked. No network required.
"""
from __future__ import annotations

import json
import pytest

from sources.schema.registry import (
    FetchMethod, ParseMode, RegistryEntry, RegistryManifest, UrlEntry,
)
from sources.schema.fetch_state import FetchStateManifest, UrlState


# ---------------------------------------------------------------------------
# UAE fixtures
# ---------------------------------------------------------------------------

_UAE_OVERLAY_RESPONSE = json.dumps({
    "jurisdiction_code": "UAE",
    "regulators": ["CBUAE"],
    "dimension_overrides": {
        "beneficial_ownership": {
            "ownership_threshold_pct": 25.0
        },
        "screening": {
            "max_screening_age_days": 180
        }
    },
    "additional_hard_reject_rules": [],
    "additional_review_rules": [],
})


@pytest.fixture()
def cbuae_source():
    """CBUAE-AML RegistryEntry with exact metadata from registry.yaml."""
    # !! FILL IN correct labels, urls, document_name, relevant_sections from step 1
    return RegistryEntry(
        id="CBUAE-AML",
        jurisdiction="UAE",
        regulator="CBUAE",
        document_name="CBUAE AML/CFT Standards for Licensed Financial Institutions",
        urls=[
            UrlEntry(
                label="landing",
                url="https://www.centralbank.ae/en/regulation/aml-cft",
                fetch_method=FetchMethod.playwright,
            ),
        ],
        parse_mode=ParseMode.llm,
        relevant_sections="Art 8 — PoA; dual-address requirement (local UAE + home country for expats); shadow listed persons; goAML reporting within 5 days",
        active=True,
    )


@pytest.fixture()
def uae_fetch_state(cbuae_source):
    """FetchStateManifest with CBUAE-AML first URL label in changed state."""
    first_label = cbuae_source.urls[0].label
    return FetchStateManifest(
        schema_version="1.0",
        generated_at="2026-01-01T00:00:00",
        states={
            "CBUAE-AML": {
                first_label: UrlState(last_status="changed")
            }
        },
    )


# ---------------------------------------------------------------------------
# IND fixtures
# ---------------------------------------------------------------------------

_IND_OVERLAY_RESPONSE = json.dumps({
    "jurisdiction_code": "IND",
    "regulators": ["RBI"],
    "dimension_overrides": {
        "beneficial_ownership": {
            "ownership_threshold_pct": 25.0
        },
        "identity": {
            "doc_expiry_warning_days": 90
        }
    },
    "additional_hard_reject_rules": [],
    "additional_review_rules": [],
})


@pytest.fixture()
def rbi_source():
    """RBI-KYC RegistryEntry with exact metadata from registry.yaml."""
    # !! FILL IN correct labels, urls, document_name, relevant_sections from step 1
    return RegistryEntry(
        id="RBI-KYC",
        jurisdiction="IND",
        regulator="RBI",
        document_name="RBI Master Direction on KYC (2016, updated)",
        urls=[
            UrlEntry(
                label="rbi",
                url="https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566",
                fetch_method=FetchMethod.http_get,
            ),
        ],
        parse_mode=ParseMode.llm,
        relevant_sections="OVDs as combined ID + PoA; Aadhaar e-KYC; V-CIP; SBO threshold 10% (vs FATF 25%); inoperative account at 2yr; DEA Fund transfer at 10yr",
        active=True,
    )


@pytest.fixture()
def ind_fetch_state(rbi_source):
    """FetchStateManifest with RBI-KYC first URL label in changed state."""
    first_label = rbi_source.urls[0].label
    return FetchStateManifest(
        schema_version="1.0",
        generated_at="2026-01-01T00:00:00",
        states={
            "RBI-KYC": {
                first_label: UrlState(last_status="changed")
            }
        },
    )


# ---------------------------------------------------------------------------
# UAE-001: CBUAE-AML found by find_changed_sources
# ---------------------------------------------------------------------------

def test_uae_001_cbuae_found_in_changed_sources(cbuae_source, uae_fetch_state):
    """UAE-001: CBUAE-AML with status=changed is returned by find_changed_sources."""
    from sources.extractor import find_changed_sources
    registry = RegistryManifest(schema_version="1.0", sources=[cbuae_source])
    result = find_changed_sources(registry, uae_fetch_state)
    assert len(result) == 1
    assert result[0].id == "CBUAE-AML"


# ---------------------------------------------------------------------------
# UAE-002: extract_source produces valid UAE overlay and writes UAE.json
# ---------------------------------------------------------------------------

def test_uae_002_extract_source_produces_and_stages_uae_overlay(
    cbuae_source, tmp_path, monkeypatch
):
    """UAE-002: extract_source returns valid UAE overlay and writes UAE.json."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from sources.extractor import extract_source
    from sources.extractor.staging import read_staging
    from rules.schema import JurisdictionOverlay

    overlay = extract_source(
        cbuae_source,
        _fetch_content_fn=lambda src: "CBUAE AML regulatory text content",
        _call_llm_fn=lambda prompt: _UAE_OVERLAY_RESPONSE,
    )

    assert overlay.jurisdiction_code == "UAE"
    assert "CBUAE" in overlay.regulators

    loaded = read_staging("UAE")
    assert isinstance(loaded, JurisdictionOverlay)


# ---------------------------------------------------------------------------
# UAE-003: run_extraction end-to-end returns UAE overlay
# ---------------------------------------------------------------------------

def test_uae_003_run_extraction_returns_uae_overlay(
    cbuae_source, uae_fetch_state, tmp_path, monkeypatch
):
    """UAE-003: run_extraction with CBUAE-AML changed returns one UAE overlay."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from sources.extractor import run_extraction

    registry = RegistryManifest(schema_version="1.0", sources=[cbuae_source])
    results = run_extraction(
        registry=registry,
        fetch_state=uae_fetch_state,
        _fetch_content_fn=lambda src: "CBUAE AML regulatory text content",
        _call_llm_fn=lambda prompt: _UAE_OVERLAY_RESPONSE,
    )

    assert len(results) == 1
    assert results[0].jurisdiction_code == "UAE"


# ---------------------------------------------------------------------------
# IND-001: RBI-KYC found by find_changed_sources
# ---------------------------------------------------------------------------

def test_ind_001_rbi_found_in_changed_sources(rbi_source, ind_fetch_state):
    """IND-001: RBI-KYC with status=changed is returned by find_changed_sources."""
    from sources.extractor import find_changed_sources
    registry = RegistryManifest(schema_version="1.0", sources=[rbi_source])
    result = find_changed_sources(registry, ind_fetch_state)
    assert len(result) == 1
    assert result[0].id == "RBI-KYC"


# ---------------------------------------------------------------------------
# IND-002: extract_source produces valid IND overlay and writes IND.json
# ---------------------------------------------------------------------------

def test_ind_002_extract_source_produces_and_stages_ind_overlay(
    rbi_source, tmp_path, monkeypatch
):
    """IND-002: extract_source returns valid IND overlay and writes IND.json."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from sources.extractor import extract_source
    from sources.extractor.staging import read_staging
    from rules.schema import JurisdictionOverlay

    overlay = extract_source(
        rbi_source,
        _fetch_content_fn=lambda src: "RBI KYC Directions regulatory text content",
        _call_llm_fn=lambda prompt: _IND_OVERLAY_RESPONSE,
    )

    assert overlay.jurisdiction_code == "IND"
    assert "RBI" in overlay.regulators

    loaded = read_staging("IND")
    assert isinstance(loaded, JurisdictionOverlay)


# ---------------------------------------------------------------------------
# IND-003: run_extraction end-to-end returns IND overlay
# ---------------------------------------------------------------------------

def test_ind_003_run_extraction_returns_ind_overlay(
    rbi_source, ind_fetch_state, tmp_path, monkeypatch
):
    """IND-003: run_extraction with RBI-KYC changed returns one IND overlay."""
    import sources.extractor.staging as staging_mod
    monkeypatch.setattr(staging_mod, "_STAGING_DIR", tmp_path)

    from sources.extractor import run_extraction

    registry = RegistryManifest(schema_version="1.0", sources=[rbi_source])
    results = run_extraction(
        registry=registry,
        fetch_state=ind_fetch_state,
        _fetch_content_fn=lambda src: "RBI KYC Directions regulatory text content",
        _call_llm_fn=lambda prompt: _IND_OVERLAY_RESPONSE,
    )

    assert len(results) == 1
    assert results[0].jurisdiction_code == "IND"
