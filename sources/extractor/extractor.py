"""
Core extraction pipeline.

Flow per source
---------------
1. find_changed_sources()  — which llm sources need extraction
2. fetch_content()         — HTTP GET all non-api_status URLs, concatenate text
3. build_prompt()          — construct LLM prompt with source metadata + content
4. call_llm()              — call Claude API, return raw text
5. parse_llm_response()    — strip markdown fences, parse JSON
6. validate_overlay()      — JurisdictionOverlay.model_validate()
7. write_staging()         — persist to rules/staging/

Skipped sources
---------------
- parse_mode != llm  (direct sources have dedicated parsers; none are api_status)
- active == False
- no URL in fetch_state has last_status == "changed"
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from rules.schema import JurisdictionOverlay
from sources.schema.registry import FetchMethod, ParseMode, RegistryEntry, load_registry
from sources.schema.fetch_state import FetchStateManifest, load_fetch_state
from .staging import write_staging

logger = logging.getLogger(__name__)

_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = os.environ.get("KYC_EXTRACTOR_MODEL", "claude-opus-4-5-20251101")
_MAX_CONTENT_CHARS = 80_000   # truncate fetched content to keep prompt within context


def find_changed_sources(
    registry=None,
    fetch_state: Optional[FetchStateManifest] = None,
) -> List[RegistryEntry]:
    """Return active llm-parse sources with at least one URL whose last_status=changed."""
    if registry is None:
        registry = load_registry()
    if fetch_state is None:
        fetch_state = load_fetch_state()

    changed = []
    for source in registry.sources:
        if not source.active:
            continue
        if source.parse_mode != ParseMode.llm:
            continue
        source_states = fetch_state.states.get(source.id, {})
        if any(
            url_state.last_status == "changed"
            for url_state in source_states.values()
        ):
            changed.append(source)
    return changed


def fetch_content(source: RegistryEntry, timeout: int = 30) -> str:
    """Fetch text content for all non-api_status URLs in a source.

    Returns concatenated text. Skips URLs that fail or return non-200.
    Truncates total content to _MAX_CONTENT_CHARS.
    """
    parts: List[str] = []
    for url_entry in source.urls:
        if url_entry.fetch_method == FetchMethod.api_status:
            continue
        try:
            resp = httpx.get(
                url_entry.url,
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": "KYC-Apexon-Extractor/1.0"},
            )
            if resp.status_code == 200:
                parts.append(f"--- {url_entry.label} ({url_entry.url}) ---\n{resp.text}")
            else:
                logger.warning(
                    "fetch_content: %s returned HTTP %s", url_entry.url, resp.status_code
                )
        except Exception as exc:
            logger.warning("fetch_content: failed to fetch %s: %s", url_entry.url, exc)

    combined = "\n\n".join(parts)
    if len(combined) > _MAX_CONTENT_CHARS:
        combined = combined[:_MAX_CONTENT_CHARS] + "\n\n[CONTENT TRUNCATED]"
    return combined


def build_prompt(source: RegistryEntry, content: str) -> str:
    """Build the LLM extraction prompt for a single source."""
    return f"""You are a KYC regulatory analyst. Extract jurisdiction-specific KYC parameters from the regulatory text below.

SOURCE METADATA
---------------
Source ID:        {source.id}
Jurisdiction:     {source.jurisdiction}
Regulator:        {source.regulator}
Document:         {source.document_name}
Relevant sections: {source.relevant_sections}

EXTRACTION TASK
---------------
Produce a JSON object that conforms EXACTLY to this schema:

{{
  "jurisdiction_code": "<ISO 3166-1 alpha-3 or EU>",
  "regulators": ["<short regulator name>", ...],
  "dimension_overrides": {{
    // Include ONLY parameters that differ from FATF baseline.
    // Valid top-level keys: identity, screening, beneficial_ownership,
    //                       transactions, documents, data_quality
    // Under identity:
    //   min_verified_docs (int), doc_expiry_warning_days (int),
    //   accepted_doc_types (list of str)
    // Under screening:
    //   max_screening_age_days (int), fuzzy_match_threshold (float 0-1)
    // Under beneficial_ownership:
    //   ownership_threshold_pct (float), max_chain_depth (int)
    // Under transactions:
    //   edd_trigger_threshold_usd (float), velocity_window_days (int)
    // Under documents:
    //   max_doc_age_days (int), accepted_proof_of_address_types (list of str)
    // Under data_quality:
    //   critical_fields (list of str), poor_quality_threshold (float 0-1)
  }},
  "additional_hard_reject_rules": [],
  "additional_review_rules": []
}}

FATF BASELINE (for reference — only include overrides that differ):
- beneficial_ownership.ownership_threshold_pct: 25.0
- screening.max_screening_age_days: 365
- transactions.velocity_window_days: 90
- identity.doc_expiry_warning_days: 90
- documents.max_doc_age_days: 365

RULES
-----
1. Return ONLY the JSON object. No preamble, no explanation, no markdown fences.
2. Use null for unknown dates; omit fields you cannot determine from the text.
3. jurisdiction_code must be the ISO 3166-1 alpha-3 code for the jurisdiction
   (USA, GBR, CHE, SGP, HKG, AUS, CAN, UAE, IND) or "EU" for EU-wide directives.
4. regulators must list only the regulators whose rules appear in this document.
5. dimension_overrides must be empty {{}} if no parameters differ from FATF baseline.
6. Do not invent values not supported by the regulatory text.

REGULATORY TEXT
---------------
{content}
"""


def call_llm(prompt: str, api_key: Optional[str] = None) -> str:
    """Call the Claude API and return the raw text response.

    Uses ANTHROPIC_API_KEY env var if api_key not provided.
    Raises RuntimeError on non-200 response.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": _DEFAULT_MODEL,
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = httpx.post(_ANTHROPIC_API_URL, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Claude API returned HTTP {resp.status_code}: {resp.text[:500]}"
        )
    data = resp.json()
    return data["content"][0]["text"]


def parse_llm_response(raw: str) -> Dict[str, Any]:
    """Strip markdown code fences and parse JSON from LLM response."""
    text = raw.strip()
    # Strip ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove first line (```json or ```) and last line (```)
        inner = lines[1:] if lines[0].startswith("```") else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return json.loads(text)


def validate_overlay(data: Dict[str, Any]) -> JurisdictionOverlay:
    """Validate a dict against JurisdictionOverlay schema. Raises ValidationError on failure."""
    return JurisdictionOverlay.model_validate(data)


def extract_source(
    source: RegistryEntry,
    api_key: Optional[str] = None,
    _fetch_content_fn=None,
    _call_llm_fn=None,
) -> JurisdictionOverlay:
    """Full extraction pipeline for one source. Returns validated JurisdictionOverlay.

    _fetch_content_fn and _call_llm_fn are injection points for testing.
    """
    fetch_fn = _fetch_content_fn or fetch_content
    llm_fn = _call_llm_fn or (lambda prompt: call_llm(prompt, api_key=api_key))

    logger.info("Extracting source: %s", source.id)
    content = fetch_fn(source)
    if not content.strip():
        raise ValueError(f"No content fetched for source {source.id!r}")

    prompt = build_prompt(source, content)
    raw = llm_fn(prompt)
    data = parse_llm_response(raw)
    overlay = validate_overlay(data)

    path = write_staging(overlay)
    logger.info("Staged overlay for %s → %s", overlay.jurisdiction_code, path)
    return overlay


def run_extraction(
    source_ids: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    registry=None,
    fetch_state: Optional[FetchStateManifest] = None,
    _fetch_content_fn=None,
    _call_llm_fn=None,
) -> List[JurisdictionOverlay]:
    """Orchestrate extraction for all changed llm sources (or a named subset).

    Returns list of successfully extracted overlays.
    Errors per source are logged and skipped — does not abort the run.
    """
    if registry is None:
        registry = load_registry()
    if fetch_state is None:
        fetch_state = load_fetch_state()

    candidates = find_changed_sources(registry, fetch_state)

    if source_ids is not None:
        id_set = set(source_ids)
        candidates = [s for s in candidates if s.id in id_set]

    results: List[JurisdictionOverlay] = []
    for source in candidates:
        try:
            overlay = extract_source(
                source,
                api_key=api_key,
                _fetch_content_fn=_fetch_content_fn,
                _call_llm_fn=_call_llm_fn,
            )
            results.append(overlay)
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", source.id, exc)

    return results
