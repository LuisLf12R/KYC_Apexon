"""P8-A: Verify reviewed_by is non-null on all changelog entries."""
import json
from pathlib import Path

import pytest

RULESET_PATH = Path("rules/kyc_rules_v2.0.json")


class TestReviewedByBackfill:
    """P8-A reviewed_by backfill tests."""

    @pytest.fixture(autouse=True)
    def load_ruleset(self):
        raw = json.loads(RULESET_PATH.read_text())
        self.changelog = raw.get("changelog", [])

    def test_rb_001_no_null_reviewed_by(self):
        """RB-001: No changelog entry has reviewed_by=None."""
        nulls = [e for e in self.changelog if e.get("reviewed_by") is None]
        assert len(nulls) == 0, (
            f"{len(nulls)} changelog entries still have reviewed_by=None"
        )

    def test_rb_002_all_reviewed_by_is_string(self):
        """RB-002: Every reviewed_by value is a non-empty string."""
        for entry in self.changelog:
            val = entry.get("reviewed_by")
            assert isinstance(val, str) and len(val.strip()) > 0, (
                f"reviewed_by is not a non-empty string: {val!r}"
            )

    def test_rb_003_reviewer_name_correct(self):
        """RB-003: All entries have the expected reviewer name."""
        for entry in self.changelog:
            assert entry["reviewed_by"] == "NYU RegTech Team", (
                f"Unexpected reviewer: {entry['reviewed_by']!r}"
            )
