"""
P4-3 — fetch_state schema and init_state tests.

Coverage:
  FS-001  FetchStateManifest with empty states validates
  FS-002  UrlState all-null is valid (initial seed state)
  FS-003  UrlState with valid FetchStatus values validates
  FS-004  UrlState with invalid status raises ValidationError
  FS-005  load_fetch_state returns empty manifest when file absent
  FS-006  init_state seeds all active source/url pairs with null UrlState
  FS-007  init_state skips inactive sources (PBOC-AML must not appear)
  FS-008  init_state is idempotent — re-running does not overwrite existing data
"""

import os
import tempfile

import pytest
import yaml
from pydantic import ValidationError

from sources.schema.fetch_state import (
    FetchStateManifest,
    FetchStatus,
    UrlState,
    load_fetch_state,
    save_fetch_state,
)
from sources.fetcher.init_state import init_state
from sources.schema.registry import load_registry


# ── helpers ───────────────────────────────────────────────────────────────────

def _tmp_state_path(tmp_path):
    return str(tmp_path / "fetch_state.yaml")


def _tmp_registry_path():
    """Return the real registry path."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "sources", "registry.yaml")


# ── FS-001 to FS-005: schema validation ───────────────────────────────────────

class TestFetchStateSchema:
    def test_fs_001_empty_states_manifest_valid(self):
        m = FetchStateManifest(
            schema_version="1.0",
            generated_at="2026-04-20T00:00:00",
            states={},
        )
        assert m.states == {}

    def test_fs_002_url_state_all_null_valid(self):
        s = UrlState()
        assert s.last_fetched_at is None
        assert s.last_hash is None
        assert s.last_status is None
        assert s.last_changed_at is None
        assert s.error_message is None

    def test_fs_003_url_state_valid_status_values(self):
        for status in ("ok", "changed", "error"):
            s = UrlState(last_status=status)
            assert s.last_status == status

    def test_fs_004_url_state_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            UrlState(last_status="pending")

    def test_fs_005_load_returns_empty_manifest_when_file_absent(self, tmp_path):
        path = str(tmp_path / "nonexistent_state.yaml")
        m = load_fetch_state(path)
        assert isinstance(m, FetchStateManifest)
        assert m.states == {}


# ── FS-006 to FS-008: init_state behaviour ────────────────────────────────────

class TestInitState:
    def test_fs_006_seeds_all_active_source_url_pairs(self, tmp_path):
        state_path = _tmp_state_path(tmp_path)
        registry_path = _tmp_registry_path()

        summary = init_state(registry_path=registry_path, state_path=state_path)

        # Load what was written
        manifest = load_fetch_state(state_path)

        # Count expected pairs: active sources only
        registry = load_registry(registry_path)
        expected_pairs = sum(
            len(s.urls) for s in registry.sources if s.active
        )

        actual_pairs = sum(
            len(labels) for labels in manifest.states.values()
        )
        assert actual_pairs == expected_pairs
        assert summary["added"] == expected_pairs
        assert summary["already_present"] == 0

    def test_fs_007_skips_inactive_sources(self, tmp_path):
        state_path = _tmp_state_path(tmp_path)
        registry_path = _tmp_registry_path()

        init_state(registry_path=registry_path, state_path=state_path)
        manifest = load_fetch_state(state_path)

        # PBOC-AML is the only inactive source — must not appear in state
        assert "PBOC-AML" not in manifest.states

    def test_fs_008_idempotent_does_not_overwrite_existing_data(self, tmp_path):
        state_path = _tmp_state_path(tmp_path)
        registry_path = _tmp_registry_path()

        # First run — seeds everything
        init_state(registry_path=registry_path, state_path=state_path)

        # Simulate fetcher writing real data to one entry
        manifest = load_fetch_state(state_path)
        first_source_id = next(iter(manifest.states))
        first_label = next(iter(manifest.states[first_source_id]))
        manifest.states[first_source_id][first_label] = UrlState(
            last_fetched_at="2026-04-20T10:00:00",
            last_hash="abc123",
            last_status="ok",
        )
        save_fetch_state(manifest, state_path)

        # Second run — must not overwrite the entry we just wrote
        summary = init_state(registry_path=registry_path, state_path=state_path)
        manifest2 = load_fetch_state(state_path)

        assert manifest2.states[first_source_id][first_label].last_hash == "abc123"
        assert manifest2.states[first_source_id][first_label].last_status == "ok"
        assert summary["already_present"] > 0
