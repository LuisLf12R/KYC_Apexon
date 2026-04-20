"""
P4-4 — Fetcher unit tests (all network calls mocked).

Coverage:
  FT-001  http_head — ok response, hash computed
  FT-002  http_head — changed headers -> status=changed via update logic
  FT-003  http_get — computes SHA-256 of body bytes
  FT-004  api_status — ok response -> status=ok, hash=None
  FT-005  api_status — HTTP error -> status=error, error_message populated
  FT-006  network exception -> status=error, previous hash preserved
  FT-007  first fetch (no prior hash) -> status=changed
  FT-008  playwright falls back to http_get when not installed
  FT-009  fetch_source updates state manifest for multi-url source
  FT-010  inactive source is not fetched by fetch_all
"""

import hashlib
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import httpx

from sources.schema.registry import FetchMethod, UrlEntry
from sources.schema.fetch_state import FetchStatus, FetchStateManifest, UrlState
from sources.fetcher.fetcher import (
    FetchResult,
    _fetch_http_head,
    _fetch_http_get,
    _fetch_api_status,
    _fetch_playwright,
    _update_url_state,
    fetch_source,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_head_response(etag='"abc"', content_length='1234',
                        last_modified='Mon, 01 Jan 2026 00:00:00 GMT'):
    resp = MagicMock(spec=httpx.Response)
    resp.headers = {
        "etag": etag,
        "content-length": content_length,
        "last-modified": last_modified,
    }
    resp.raise_for_status = MagicMock()
    return resp


def _mock_get_response(body=b"hello world", status=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.content = body
    resp.raise_for_status = MagicMock()
    return resp


def _expected_head_hash(etag, cl, lm):
    raw = f"{etag}|{cl}|{lm}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _expected_body_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _make_url_entry(label="main", url="https://example.com",
                    method=FetchMethod.http_get):
    return UrlEntry(label=label, url=url, fetch_method=method)


def _blank_manifest() -> FetchStateManifest:
    return FetchStateManifest(
        schema_version="1.0",
        generated_at="2026-04-20T00:00:00",
        states={},
    )


NOW = datetime.now(timezone.utc).isoformat()


# ── FT-001 / FT-002: http_head ────────────────────────────────────────────────

class TestHttpHead:
    def test_ft_001_ok_response_hash_computed(self):
        resp = _mock_head_response()
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.head.return_value = resp
            result = _fetch_http_head("https://example.com")
        assert result.status == FetchStatus.ok
        assert result.hash is not None
        assert result.error_message is None

    def test_ft_002_changed_headers_detected_via_update_logic(self):
        old_hash = _expected_head_hash('"aaa"', '100', 'old')
        new_hash = _expected_head_hash('"bbb"', '200', 'new')
        existing = UrlState(last_hash=old_hash)
        result = FetchResult(hash=new_hash, status=FetchStatus.ok,
                             error_message=None)
        updated = _update_url_state(existing, result, NOW)
        assert updated.last_status == FetchStatus.changed.value
        assert updated.last_changed_at == NOW
        assert updated.last_hash == new_hash


# ── FT-003: http_get ──────────────────────────────────────────────────────────

class TestHttpGet:
    def test_ft_003_computes_sha256_of_body(self):
        body = b"regulatory content here"
        resp = _mock_get_response(body=body)
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.get.return_value = resp
            result = _fetch_http_get("https://example.com/doc")
        assert result.hash == _expected_body_hash(body)
        assert result.status == FetchStatus.ok


# ── FT-004 / FT-005: api_status ───────────────────────────────────────────────

class TestApiStatus:
    def test_ft_004_ok_response_no_hash(self):
        resp = _mock_get_response(body=b"")
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.get.return_value = resp
            result = _fetch_api_status("https://api.example.com/health")
        assert result.status == FetchStatus.ok
        assert result.hash is None
        assert result.error_message is None

    def test_ft_005_http_error_sets_error_status(self):
        resp = _mock_get_response(status=503)
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=resp
        )
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value.get.return_value = resp
            result = _fetch_api_status("https://api.example.com/health")
        assert result.status == FetchStatus.error
        assert result.error_message is not None


# ── FT-006: network exception ─────────────────────────────────────────────────

class TestNetworkError:
    def test_ft_006_exception_preserves_prior_hash(self):
        prior_hash = "deadbeef" * 8
        existing = UrlState(last_hash=prior_hash, last_status="ok")
        result = FetchResult(hash=None, status=FetchStatus.error,
                             error_message="timeout")
        updated = _update_url_state(existing, result, NOW)
        assert updated.last_status == FetchStatus.error.value
        assert updated.last_hash == prior_hash
        assert updated.error_message == "timeout"


# ── FT-007: first fetch ───────────────────────────────────────────────────────

class TestFirstFetch:
    def test_ft_007_first_fetch_no_prior_hash_is_changed(self):
        existing = UrlState()
        result = FetchResult(hash="newhash123", status=FetchStatus.ok,
                             error_message=None)
        updated = _update_url_state(existing, result, NOW)
        assert updated.last_status == FetchStatus.changed.value
        assert updated.last_changed_at == NOW


# ── FT-008: playwright fallback ───────────────────────────────────────────────

class TestPlaywrightFallback:
    def test_ft_008_falls_back_to_http_get_when_playwright_missing(self):
        body = b"rendered page content"
        resp = _mock_get_response(body=body)
        with patch.dict(sys.modules,
                        {"playwright": None,
                         "playwright.sync_api": None}):
            with patch("httpx.Client") as mock_cls:
                mock_cls.return_value.__enter__.return_value.get.return_value = resp
                result = _fetch_playwright("https://example.com/js-page")
        assert result.status == FetchStatus.ok
        assert result.hash == _expected_body_hash(body)


# ── FT-009: fetch_source ──────────────────────────────────────────────────────

class TestFetchSource:
    def test_ft_009_fetch_source_updates_manifest_for_multi_url_source(self):
        from sources.schema.registry import RegistryEntry, ParseMode

        source = RegistryEntry(
            id="TEST-MULTI",
            jurisdiction="TEST",
            regulator="TestReg",
            document_name="Test Doc",
            urls=[
                UrlEntry(label="landing", url="https://example.com",
                         fetch_method=FetchMethod.http_get),
                UrlEntry(label="pdf", url="https://example.com/doc.pdf",
                         fetch_method=FetchMethod.http_head),
            ],
            parse_mode=ParseMode.llm,
            relevant_sections="All",
            active=True,
        )
        manifest = _blank_manifest()
        body = b"page content"
        head_hash = _expected_head_hash('"abc"', '1234', 'Mon')

        def mock_fetch_url(url_entry):
            if url_entry.fetch_method == FetchMethod.http_get:
                return FetchResult(hash=_expected_body_hash(body),
                                   status=FetchStatus.ok, error_message=None)
            return FetchResult(hash=head_hash, status=FetchStatus.ok,
                               error_message=None)

        with patch("sources.fetcher.fetcher.fetch_url",
                   side_effect=mock_fetch_url):
            updated = fetch_source(source, manifest)

        assert "TEST-MULTI" in updated.states
        assert "landing" in updated.states["TEST-MULTI"]
        assert "pdf" in updated.states["TEST-MULTI"]
        assert updated.states["TEST-MULTI"]["landing"].last_status == FetchStatus.changed.value
        assert updated.states["TEST-MULTI"]["pdf"].last_status == FetchStatus.changed.value


# ── FT-010: fetch_all skips inactive ──────────────────────────────────────────

class TestFetchAll:
    def test_ft_010_inactive_source_not_fetched(self, tmp_path):
        import pathlib
        from sources.fetcher.fetcher import fetch_all
        from sources.schema.fetch_state import load_fetch_state

        registry_path = str(
            pathlib.Path(__file__).parent.parent / "sources" / "registry.yaml"
        )
        state_path = str(tmp_path / "fetch_state.yaml")

        with patch("sources.fetcher.fetcher.fetch_url") as mock_fetch:
            mock_fetch.return_value = FetchResult(
                hash="testhash123", status=FetchStatus.ok, error_message=None
            )
            fetch_all(registry_path=registry_path, state_path=state_path)

        manifest = load_fetch_state(state_path)
        assert "PBOC-AML" not in manifest.states
