"""P8-G: Verify MonitoringService dashboard wiring and cron config."""
from pathlib import Path


class TestMonitoringDashboard:
    """P8-G monitoring dashboard and cron tests."""

    def test_md_001_monitoring_tab_module_exists(self):
        """MD-001: monitoring tab module exists and is importable."""
        tab_path = Path("kyc_dashboard/tabs/monitoring.py")
        assert tab_path.exists(), "kyc_dashboard/tabs/monitoring.py not found"

    def test_md_002_monitoring_tab_has_render_function(self):
        """MD-002: monitoring tab exposes a callable render/show function."""
        source = Path("kyc_dashboard/tabs/monitoring.py").read_text()
        assert "def " in source, "monitoring.py has no function definitions"
        has_render = (
            "def render" in source
            or "def show" in source
            or "def display" in source
            or "def run" in source
        )
        assert has_render, (
            "monitoring.py needs a render/show/display/run function matching the tab pattern"
        )

    def test_md_003_monitoring_tab_imports_service(self):
        """MD-003: monitoring tab imports MonitoringService."""
        source = Path("kyc_dashboard/tabs/monitoring.py").read_text()
        assert "MonitoringService" in source, (
            "monitoring.py does not reference MonitoringService"
        )

    def test_md_004_monitoring_tab_uses_session_state(self):
        """MD-004: monitoring tab uses st.session_state for snapshot persistence."""
        source = Path("kyc_dashboard/tabs/monitoring.py").read_text()
        assert "session_state" in source, (
            "monitoring.py does not use session_state for snapshot persistence"
        )

    def test_md_005_main_registers_monitoring_tab(self):
        """MD-005: main.py references the monitoring tab."""
        source = Path("kyc_dashboard/main.py").read_text()
        assert "monitoring" in source.lower() or "Monitoring" in source, (
            "main.py does not reference monitoring tab"
        )

    def test_md_006_cron_workflow_exists(self):
        """MD-006: GitHub Actions workflow file exists."""
        wf = Path(".github/workflows/weekly_monitoring.yml")
        assert wf.exists(), ".github/workflows/weekly_monitoring.yml not found"

    def test_md_007_cron_schedule_is_weekly(self):
        """MD-007: Workflow contains a weekly cron schedule."""
        wf = Path(".github/workflows/weekly_monitoring.yml").read_text()
        assert "cron:" in wf, "Workflow missing cron schedule"
        assert "0 6 * * 1" in wf, "Cron expression doesn't look weekly"

    def test_md_008_cron_has_manual_trigger(self):
        """MD-008: Workflow supports manual trigger via workflow_dispatch."""
        wf = Path(".github/workflows/weekly_monitoring.yml").read_text()
        assert "workflow_dispatch" in wf, "Workflow missing workflow_dispatch trigger"
