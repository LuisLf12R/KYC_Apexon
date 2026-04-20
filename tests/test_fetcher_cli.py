"""Smoke tests for fetch_all CLI entrypoint (FTC-001)."""
import subprocess
import sys


def test_fetcher_cli_dry_run_exits_zero():
    """FTC-001: --dry-run flag prints sources and exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "sources.fetcher.fetcher", "--dry-run"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": "."},
    )
    assert result.returncode == 0, result.stderr
    assert "Dry run" in result.stdout
    assert "source(s)" in result.stdout
