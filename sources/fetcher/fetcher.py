"""
fetcher.py — dispatches HTTP fetches for each active source URL,
computes content hashes, and updates fetch_state.yaml.

Fetch methods
-------------
http_head   — HEAD request; hash of ETag + Content-Length + Last-Modified headers
http_get    — GET request; SHA-256 of response body bytes
api_status  — GET request; records ok/error only, no hash (no content to extract)
playwright  — renders JS page, hashes visible text; falls back to http_get
              with a WARNING if Playwright is not installed

Public API
----------
fetch_url(url_entry)  -> FetchResult
fetch_source(source, state_manifest) -> updated state_manifest
fetch_all(registry_path, state_path) -> summary dict
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from sources.schema.registry import FetchMethod, RegistryEntry, UrlEntry, load_registry
from sources.schema.fetch_state import (
    FetchStatus,
    FetchStateManifest,
    UrlState,
    load_fetch_state,
    save_fetch_state,
)

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)
_HEADERS = {"User-Agent": "KYC-Apexon-Fetcher/1.0 (regulatory source monitor)"}


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class FetchResult:
    hash: Optional[str]          # hex digest, or None for api_status
    status: FetchStatus
    error_message: Optional[str]


# ── per-method fetch functions ────────────────────────────────────────────────

def _hash_head_response(response: httpx.Response) -> str:
    """Hash the ETag + Content-Length + Last-Modified headers."""
    etag = response.headers.get("etag", "")
    cl = response.headers.get("content-length", "")
    lm = response.headers.get("last-modified", "")
    raw = f"{etag}|{cl}|{lm}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fetch_http_head(url: str) -> FetchResult:
    try:
        with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
            response = client.head(url)
        response.raise_for_status()
        return FetchResult(
            hash=_hash_head_response(response),
            status=FetchStatus.ok,
            error_message=None,
        )
    except Exception as exc:
        return FetchResult(hash=None, status=FetchStatus.error, error_message=str(exc))


def _fetch_http_get(url: str) -> FetchResult:
    try:
        with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
            response = client.get(url)
        response.raise_for_status()
        digest = hashlib.sha256(response.content).hexdigest()
        return FetchResult(hash=digest, status=FetchStatus.ok, error_message=None)
    except Exception as exc:
        return FetchResult(hash=None, status=FetchStatus.error, error_message=str(exc))


def _fetch_api_status(url: str) -> FetchResult:
    """Health-check only — no hash, no content extraction."""
    try:
        with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
            response = client.get(url)
        response.raise_for_status()
        return FetchResult(hash=None, status=FetchStatus.ok, error_message=None)
    except Exception as exc:
        return FetchResult(hash=None, status=FetchStatus.error, error_message=str(exc))


def _fetch_playwright(url: str) -> FetchResult:
    """Render JS page and hash visible text. Falls back to http_get if unavailable."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        logger.warning(
            "Playwright not installed — falling back to http_get for %s. "
            "Install playwright + browsers for full JS rendering support.",
            url,
        )
        return _fetch_http_get(url)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            text = page.inner_text("body")
            browser.close()
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return FetchResult(hash=digest, status=FetchStatus.ok, error_message=None)
    except Exception as exc:
        return FetchResult(hash=None, status=FetchStatus.error, error_message=str(exc))


# ── dispatch ──────────────────────────────────────────────────────────────────

_DISPATCH = {
    FetchMethod.http_head: _fetch_http_head,
    FetchMethod.http_get: _fetch_http_get,
    FetchMethod.api_status: _fetch_api_status,
    FetchMethod.playwright: _fetch_playwright,
    FetchMethod.rss: _fetch_http_get,  # RSS feeds are plain HTTP GET
}


def fetch_url(url_entry: UrlEntry) -> FetchResult:
    """Fetch a single URL and return a FetchResult."""
    handler = _DISPATCH[url_entry.fetch_method]
    return handler(url_entry.url)


# ── state update logic ────────────────────────────────────────────────────────

def _update_url_state(
    existing: UrlState,
    result: FetchResult,
    now_iso: str,
) -> UrlState:
    """Merge a FetchResult into an existing UrlState."""
    if result.status == FetchStatus.error:
        return UrlState(
            last_fetched_at=now_iso,
            last_hash=existing.last_hash,          # preserve last good hash
            last_status=FetchStatus.error,
            last_changed_at=existing.last_changed_at,
            error_message=result.error_message,
        )

    # ok or changed — determine if content actually changed
    prev_hash = existing.last_hash
    new_hash = result.hash

    if new_hash is not None and prev_hash is not None and new_hash != prev_hash:
        final_status = FetchStatus.changed
        changed_at = now_iso
    elif prev_hash is None and new_hash is not None:
        # First successful fetch — record as changed so Phase 5 extracts it
        final_status = FetchStatus.changed
        changed_at = now_iso
    else:
        final_status = FetchStatus.ok
        changed_at = existing.last_changed_at

    return UrlState(
        last_fetched_at=now_iso,
        last_hash=new_hash if new_hash is not None else existing.last_hash,
        last_status=final_status,
        last_changed_at=changed_at,
        error_message=None,
    )


# ── public API ────────────────────────────────────────────────────────────────

def fetch_source(
    source: RegistryEntry,
    state_manifest: FetchStateManifest,
) -> FetchStateManifest:
    """Fetch all URLs for one source and update state_manifest in place."""
    now_iso = datetime.now(timezone.utc).isoformat()

    if source.id not in state_manifest.states:
        state_manifest.states[source.id] = {}

    for url_entry in source.urls:
        label = url_entry.label
        existing = state_manifest.states[source.id].get(label, UrlState())

        logger.info("Fetching %s / %s (%s)", source.id, label, url_entry.url)
        result = fetch_url(url_entry)

        state_manifest.states[source.id][label] = _update_url_state(
            existing, result, now_iso
        )

        if result.status == FetchStatus.error:
            logger.warning(
                "Error fetching %s / %s: %s", source.id, label, result.error_message
            )
        else:
            logger.info(
                "Fetched %s / %s — status=%s hash=%s",
                source.id, label,
                state_manifest.states[source.id][label].last_status,
                (result.hash or "")[:12],
            )

    return state_manifest


def fetch_all(
    registry_path: str | os.PathLike | None = None,
    state_path: str | os.PathLike | None = None,
) -> dict:
    """Fetch all active sources, update fetch_state.yaml, return summary."""
    registry = load_registry(registry_path)
    state_manifest = load_fetch_state(state_path)

    active_sources = [s for s in registry.sources if s.active]
    changed = 0
    errors = 0

    for source in active_sources:
        state_manifest = fetch_source(source, state_manifest)
        for url_entry in source.urls:
            url_state = state_manifest.states[source.id][url_entry.label]
            if url_state.last_status == FetchStatus.changed.value:
                changed += 1
            elif url_state.last_status == FetchStatus.error.value:
                errors += 1

    state_manifest.generated_at = datetime.now(timezone.utc).isoformat()
    save_fetch_state(state_manifest, state_path)

    return {
        "active_sources": len(active_sources),
        "changed": changed,
        "errors": errors,
    }
