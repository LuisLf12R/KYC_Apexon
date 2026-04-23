"""P9-B: UBO ongoing monitoring — change detection tests."""
import pandas as pd
import pytest

from sources.monitoring.ubo_monitoring import (
    UBOMonitoringService,
    UBOMonitoringReport,
    UBOChange,
)


@pytest.fixture
def svc():
    return UBOMonitoringService()


def _make_ubo_df(rows):
    """Build a minimal UBO DataFrame from list of dicts."""
    if not rows:
        return pd.DataFrame(columns=["customer_id", "owner_name", "ownership_pct", "is_individual"])
    return pd.DataFrame(rows)


class TestUBOMonitoring:
    """P9-B UBO change detection tests."""

    def test_ubo_mon_001_no_changes(self, svc):
        """UMON-001: Identical snapshot and current → no changes."""
        df = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "50", "is_individual": "True"},
            {"customer_id": "C1", "owner_name": "Bob", "ownership_pct": "50", "is_individual": "True"},
        ])
        snap = svc.snapshot(df)
        report = svc.check(snap, df)
        assert report.change_count == 0
        assert report.customer_count == 0

    def test_ubo_mon_002_ubo_added(self, svc):
        """UMON-002: New UBO record added → detected as ubo_added."""
        prev = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "100", "is_individual": "True"},
        ])
        curr = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "60", "is_individual": "True"},
            {"customer_id": "C1", "owner_name": "Bob", "ownership_pct": "40", "is_individual": "True"},
        ])
        snap = svc.snapshot(prev)
        report = svc.check(snap, curr)
        added = [c for c in report.changes if c.change_type == "ubo_added"]
        assert len(added) >= 1
        assert added[0].owner_name == "Bob"
        assert "C1" in report.affected_customer_ids

    def test_ubo_mon_003_ubo_removed(self, svc):
        """UMON-003: UBO record removed → detected as ubo_removed."""
        prev = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "60", "is_individual": "True"},
            {"customer_id": "C1", "owner_name": "Bob", "ownership_pct": "40", "is_individual": "True"},
        ])
        curr = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "100", "is_individual": "True"},
        ])
        snap = svc.snapshot(prev)
        report = svc.check(snap, curr)
        removed = [c for c in report.changes if c.change_type == "ubo_removed"]
        assert len(removed) >= 1
        assert removed[0].owner_name == "Bob"
        assert "C1" in report.affected_customer_ids

    def test_ubo_mon_004_ownership_changed(self, svc):
        """UMON-004: Ownership percentage change → detected as ownership_changed."""
        prev = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "60", "is_individual": "True"},
        ])
        curr = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "80", "is_individual": "True"},
        ])
        snap = svc.snapshot(prev)
        report = svc.check(snap, curr)
        changed = [c for c in report.changes if c.change_type == "ownership_changed"]
        assert len(changed) == 1
        assert "60" in changed[0].previous_value
        assert "80" in changed[0].current_value

    def test_ubo_mon_005_multiple_customers(self, svc):
        """UMON-005: Changes across multiple customers are tracked independently."""
        prev = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "100", "is_individual": "True"},
            {"customer_id": "C2", "owner_name": "Carol", "ownership_pct": "100", "is_individual": "True"},
        ])
        curr = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "100", "is_individual": "True"},
            {"customer_id": "C2", "owner_name": "Carol", "ownership_pct": "70", "is_individual": "True"},
            {"customer_id": "C2", "owner_name": "Dave", "ownership_pct": "30", "is_individual": "True"},
        ])
        snap = svc.snapshot(prev)
        report = svc.check(snap, curr)
        assert "C2" in report.affected_customer_ids
        assert "C1" not in report.affected_customer_ids

    def test_ubo_mon_006_empty_snapshot(self, svc):
        """UMON-006: Empty previous snapshot → all current records are ubo_added."""
        curr = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "100", "is_individual": "True"},
        ])
        report = svc.check([], curr)
        assert report.change_count == 1
        assert report.changes[0].change_type == "ubo_added"

    def test_ubo_mon_007_empty_current(self, svc):
        """UMON-007: Empty current DataFrame → all snapshot records are ubo_removed."""
        prev = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "100", "is_individual": "True"},
        ])
        snap = svc.snapshot(prev)
        curr = _make_ubo_df([])
        report = svc.check(snap, curr)
        assert report.change_count == 1
        assert report.changes[0].change_type == "ubo_removed"

    def test_ubo_mon_008_report_summary(self, svc):
        """UMON-008: Report summary dict has expected keys."""
        report = UBOMonitoringReport()
        s = report.summary()
        assert "change_count" in s
        assert "affected_customer_ids" in s
        assert "changes_by_type" in s

    def test_ubo_mon_009_details_changed(self, svc):
        """UMON-009: is_individual field change → detected as ubo_details_changed."""
        prev = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "100", "is_individual": "True"},
        ])
        curr = _make_ubo_df([
            {"customer_id": "C1", "owner_name": "Alice", "ownership_pct": "100", "is_individual": "False"},
        ])
        snap = svc.snapshot(prev)
        report = svc.check(snap, curr)
        detail_changes = [c for c in report.changes if c.change_type == "ubo_details_changed"]
        assert len(detail_changes) == 1

    def test_ubo_mon_010_dashboard_tab_references_ubo(self):
        """UMON-010: Dashboard monitoring tab references UBOMonitoringService."""
        from pathlib import Path
        source = Path("kyc_dashboard/tabs/monitoring.py").read_text()
        assert "UBOMonitoringService" in source
