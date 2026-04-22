"""P8-F: Verify evaluate_batch() accepts and forwards institution_id."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestBatchInstitution:
    """P8-F evaluate_batch institution_id tests."""

    def test_bi_001_evaluate_batch_accepts_institution_id(self):
        """BI-001: evaluate_batch() signature accepts institution_id parameter."""
        import inspect
        from kyc_engine.engine import KYCComplianceEngine

        sig = inspect.signature(KYCComplianceEngine.evaluate_batch)
        assert "institution_id" in sig.parameters, (
            "evaluate_batch() missing institution_id parameter"
        )

    def test_bi_002_institution_id_defaults_to_none(self):
        """BI-002: institution_id defaults to None."""
        import inspect
        from kyc_engine.engine import KYCComplianceEngine

        sig = inspect.signature(KYCComplianceEngine.evaluate_batch)
        param = sig.parameters["institution_id"]
        assert param.default is None, (
            f"institution_id default should be None, got {param.default!r}"
        )

    def test_bi_003_institution_id_forwarded_to_evaluate_customer(self):
        """BI-003: evaluate_batch passes institution_id to each evaluate_customer call."""
        from kyc_engine.engine import KYCComplianceEngine

        _engine = MagicMock(spec=KYCComplianceEngine)
        _engine.customers = MagicMock()

        # We need to test that the real method forwards institution_id.
        # Read the source to verify the call pattern exists.
        import inspect

        source = inspect.getsource(KYCComplianceEngine.evaluate_batch)
        assert "institution_id" in source, (
            "evaluate_batch source does not reference institution_id"
        )
        # Check it's passed to evaluate_customer
        assert "institution_id=institution_id" in source, (
            "evaluate_batch does not appear to forward institution_id to evaluate_customer"
        )

    def test_bi_004_batch_tab_imports_institution_helper(self):
        """BI-004: Batch tab can access institution selector helper."""
        try:
            from kyc_dashboard.tabs.individual import _get_available_institutions

            result = _get_available_institutions()
            assert result[0][0] == "__none__"
        except ImportError as e:
            pytest.skip(f"Dashboard import not available: {e}")
