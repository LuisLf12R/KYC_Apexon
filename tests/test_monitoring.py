"""
tests/test_monitoring.py
P7-I — Ongoing monitoring trigger.
Tests MonitoringService without requiring a live fetch_state.yaml —
patches _fetch_state_as_dict and the registry to use synthetic data.
"""

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from sources.monitoring.monitoring import MonitoringService, MonitoringReport, SourceChange


def _make_service():
    """
    Build a MonitoringService with mocked registry and fetch_state
    so tests run without a live fetch_state.yaml on disk.
    """
    with patch("sources.monitoring.monitoring.MonitoringService.__init__", lambda self: None):
        svc = MonitoringService.__new__(MonitoringService)

    # Minimal registry entry
    mock_entry = MagicMock()
    mock_entry.id = "OFAC-SDN"
    mock_entry.jurisdiction = "USA"
    mock_entry.urls = [MagicMock()]

    mock_registry = MagicMock()
    mock_registry.sources = [mock_entry]
    svc._registry = mock_registry
    svc._fetch_state = MagicMock()
    svc._source_jurisdiction = {"OFAC-SDN": "USA", "OFSI-CONS": "GBR"}
    return svc


def _customers(*jurisdictions):
    return pd.DataFrame([
        {"customer_id": f"C{i:03d}", "jurisdiction": jur}
        for i, jur in enumerate(jurisdictions, 1)
    ])


# MON-001: no changes when snapshot matches current state
def test_mon_001_no_changes():
    svc = _make_service()
    current = {
        "OFAC-SDN": {"content_hash": "abc123", "last_fetched_at": "2026-04-01T00:00:00"},
    }
    svc._fetch_state_as_dict = lambda: current

    report = svc.check(
        previous_snapshot=current.copy(),
        customers_df=_customers("USA"),
    )
    assert report.change_count == 0
    assert report.customer_count == 0


# MON-002: hash change detected and mapped to customers
def test_mon_002_hash_change_maps_customers():
    svc = _make_service()
    current = {
        "OFAC-SDN": {"content_hash": "new_hash", "last_fetched_at": "2026-04-02T00:00:00"},
    }
    svc._fetch_state_as_dict = lambda: current

    previous = {
        "OFAC-SDN": {"content_hash": "old_hash", "last_fetched_at": "2026-04-01T00:00:00"},
    }

    report = svc.check(
        previous_snapshot=previous,
        customers_df=_customers("USA", "GBR", "USA"),
    )

    assert report.change_count == 1
    assert report.changed_sources[0].change_type == "hash_changed"
    assert report.changed_sources[0].source_id == "OFAC-SDN"
    assert "USA" in report.affected_jurisdictions
    assert "C001" in report.customer_ids_to_review
    assert "C003" in report.customer_ids_to_review
    assert "C002" not in report.customer_ids_to_review  # GBR not affected


# MON-003: new source (not in previous snapshot) flagged as new_fetch
def test_mon_003_new_source_flagged():
    svc = _make_service()
    current = {
        "OFAC-SDN": {"content_hash": "abc", "last_fetched_at": "2026-04-01T00:00:00"},
    }
    svc._fetch_state_as_dict = lambda: current

    report = svc.check(
        previous_snapshot={},   # empty — source is new
        customers_df=_customers("USA"),
    )

    assert report.change_count == 1
    assert report.changed_sources[0].change_type == "new_fetch"


# MON-004: timestamp-only change detected as status_changed
def test_mon_004_timestamp_change():
    svc = _make_service()
    current = {
        "OFAC-SDN": {"content_hash": "abc", "last_fetched_at": "2026-04-02T00:00:00"},
    }
    svc._fetch_state_as_dict = lambda: current

    previous = {
        "OFAC-SDN": {"content_hash": "abc", "last_fetched_at": "2026-04-01T00:00:00"},
    }

    report = svc.check(
        previous_snapshot=previous,
        customers_df=_customers("USA"),
    )
    assert report.change_count == 1
    assert report.changed_sources[0].change_type == "status_changed"


# MON-005: empty customers_df returns empty customer list
def test_mon_005_empty_customers():
    svc = _make_service()
    current = {
        "OFAC-SDN": {"content_hash": "new", "last_fetched_at": "2026-04-02T00:00:00"},
    }
    svc._fetch_state_as_dict = lambda: current

    report = svc.check(
        previous_snapshot={"OFAC-SDN": {"content_hash": "old", "last_fetched_at": "2026-04-01"}},
        customers_df=pd.DataFrame(),
    )
    assert report.change_count == 1
    assert report.customer_count == 0


# MON-006: summary() returns expected keys
def test_mon_006_summary_shape():
    svc = _make_service()
    svc._fetch_state_as_dict = lambda: {}
    report = svc.check(previous_snapshot={}, customers_df=pd.DataFrame())
    summary = report.summary()
    for key in ("change_count", "affected_jurisdictions", "customer_ids_to_review", "skipped_sources"):
        assert key in summary, f"Missing key: {key}"


# MON-007: snapshot() returns a dict
def test_mon_007_snapshot_returns_dict():
    svc = _make_service()
    svc._fetch_state_as_dict = lambda: {"OFAC-SDN": {"content_hash": "x", "last_fetched_at": "t"}}
    snap = svc.snapshot()
    assert isinstance(snap, dict)
    assert "OFAC-SDN" in snap
