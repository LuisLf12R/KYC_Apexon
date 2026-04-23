"""
Tests for dashboard institution config awareness.
Test IDs: ID-001 through ID-006.
"""
import os
import pytest
from unittest.mock import patch


class TestInstitutionDashboardConfig:
    """ID-001..006: dashboard institution config helpers."""

    def test_id001_get_configured_returns_env_var(self):
        """ID-001: get_configured_institution returns env var value."""
        with patch.dict(os.environ, {"KYC_INSTITUTION_ID": "INST_ALPHA"}):
            from kyc_dashboard.components import get_configured_institution
            assert get_configured_institution() == "INST_ALPHA"

    def test_id002_get_configured_returns_none_when_unset(self):
        """ID-002: get_configured_institution returns None without env var."""
        env = os.environ.copy()
        env.pop("KYC_INSTITUTION_ID", None)
        with patch.dict(os.environ, env, clear=True):
            from kyc_dashboard.components import get_configured_institution
            assert get_configured_institution() is None

    def test_id003_empty_string_treated_as_unset(self):
        """ID-003: Empty string env var returns None."""
        with patch.dict(os.environ, {"KYC_INSTITUTION_ID": ""}):
            from kyc_dashboard.components import get_configured_institution
            assert get_configured_institution() is None

    def test_id004_whitespace_only_treated_as_unset(self):
        """ID-004: Whitespace-only env var returns None."""
        with patch.dict(os.environ, {"KYC_INSTITUTION_ID": "   "}):
            from kyc_dashboard.components import get_configured_institution
            assert get_configured_institution() is None

    def test_id005_strips_whitespace(self):
        """ID-005: Leading/trailing whitespace stripped from env var."""
        with patch.dict(os.environ, {"KYC_INSTITUTION_ID": "  INST_BETA  "}):
            from kyc_dashboard.components import get_configured_institution
            assert get_configured_institution() == "INST_BETA"

    def test_id006_helper_importable(self):
        """ID-006: Both helpers are importable from components."""
        from kyc_dashboard.components import (
            get_configured_institution,
            render_institution_banner,
        )
        assert callable(get_configured_institution)
        assert callable(render_institution_banner)
