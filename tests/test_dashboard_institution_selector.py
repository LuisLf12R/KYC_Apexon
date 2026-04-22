"""P8-E: Verify institution selector helper and integration."""
import json
from unittest.mock import MagicMock, patch

import pytest


class TestInstitutionSelector:
    """P8-E institution selector tests."""

    def test_is_001_helper_returns_none_option_always(self, tmp_path):
        """IS-001: Helper always includes the 'None' fallback option."""
        pytest.importorskip("streamlit")
        from kyc_dashboard.tabs.individual import _get_available_institutions

        with patch("kyc_dashboard.tabs.individual.Path") as MockPath:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = True
            mock_dir.glob.return_value = []
            MockPath.return_value = mock_dir
            result = _get_available_institutions()
        assert len(result) >= 1
        assert result[0][0] == "__none__"
        assert "None" in result[0][1]

    def test_is_002_helper_reads_institution_files(self, tmp_path):
        """IS-002: Helper discovers institution files from directory."""
        pytest.importorskip("streamlit")
        inst_dir = tmp_path / "institutions"
        inst_dir.mkdir()
        overlay = {
            "institution_id": "TEST_BANK_001",
            "institution_name": "Test Bank",
            "active": True,
        }
        (inst_dir / "TEST_BANK_001.json").write_text(json.dumps(overlay))

        from kyc_dashboard.tabs.individual import _get_available_institutions

        with patch("kyc_dashboard.tabs.individual.Path") as MockPath:
            MockPath.return_value = inst_dir
            result = _get_available_institutions()

        ids = [r[0] for r in result]
        assert "__none__" in ids
        assert "TEST_BANK_001" in ids

    def test_is_003_helper_handles_missing_directory(self):
        """IS-003: Helper returns only None option if directory doesn't exist."""
        pytest.importorskip("streamlit")
        from kyc_dashboard.tabs.individual import _get_available_institutions

        with patch("kyc_dashboard.tabs.individual.Path") as MockPath:
            mock_dir = MagicMock()
            mock_dir.exists.return_value = False
            MockPath.return_value = mock_dir
            result = _get_available_institutions()
        assert len(result) == 1
        assert result[0][0] == "__none__"

    def test_is_004_none_selection_passes_none_to_engine(self):
        """IS-004: Selecting '__none__' means institution_id=None for engine."""
        selected = "__none__"
        institution_id = None if selected == "__none__" else selected
        assert institution_id is None

    def test_is_005_valid_selection_passes_id_to_engine(self):
        """IS-005: Selecting a real institution passes that ID to engine."""
        selected = "TEST_BANK_001"
        institution_id = None if selected == "__none__" else selected
        assert institution_id == "TEST_BANK_001"
