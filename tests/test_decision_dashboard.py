"""Tests for Customer Decision Dashboard — Phase 11D."""

from kyc_dashboard.decision_dashboard import build_decision_dashboard


class TestBuildDecisionDashboard:
    """CDD-001 through CDD-008."""

    def _make_result(self, customer_id, disposition, scores=None, triggered_rules=None):
        result = {
            "customer_id": customer_id,
            "disposition": disposition,
            "triggered_reject_rules": triggered_rules or [],
            "triggered_review_rules": [],
            "overall_score": 82,
            "aml_screening_score": 80,
            "identity_verification_score": 85,
            "account_activity_score": 83,
            "proof_of_address_score": 84,
            "beneficial_ownership_score": 82,
            "data_quality_score": 81,
            "source_of_wealth_score": 79,
            "crs_fatca_score": 78,
        }
        if scores:
            result.update(scores)
        return result

    def test_pass_disposition_maps_correctly(self):
        # CDD-001
        results = [self._make_result("CUST-001", "PASS")]
        df = build_decision_dashboard(results)
        assert len(df) == 1
        assert df.iloc[0]["pass_or_reject"] in ["PASS", "Pass", "pass"]

    def test_reject_disposition_maps_correctly(self):
        # CDD-002
        results = [self._make_result("CUST-001", "REJECT", triggered_rules=[{"rule_id": "HR-001"}])]
        df = build_decision_dashboard(results)
        assert "REJECT" in df.iloc[0]["pass_or_reject"].upper()

    def test_review_disposition_maps_correctly(self):
        # CDD-003
        results = [self._make_result("CUST-001", "REVIEW", triggered_rules=[{"rule_id": "RV-001"}])]
        df = build_decision_dashboard(results)
        row = df.iloc[0]["pass_or_reject"].upper()
        assert "REVIEW" in row

    def test_confidence_level_present(self):
        # CDD-004
        results = [self._make_result("CUST-001", "PASS")]
        df = build_decision_dashboard(results)
        assert "confidence_level" in df.columns
        assert df.iloc[0]["confidence_level"] is not None

    def test_notes_generated_for_review(self):
        # CDD-005
        results = [self._make_result("CUST-001", "REVIEW", triggered_rules=[{"rule_id": "RV-006"}])]
        df = build_decision_dashboard(results)
        assert "notes" in df.columns
        notes = str(df.iloc[0]["notes"])
        assert len(notes) > 0

    def test_multiple_customers(self):
        # CDD-006
        results = [
            self._make_result("CUST-001", "PASS"),
            self._make_result("CUST-002", "REVIEW", triggered_rules=[{"rule_id": "RV-001"}]),
            self._make_result("CUST-003", "REJECT", triggered_rules=[{"rule_id": "HR-001"}]),
        ]
        df = build_decision_dashboard(results)
        assert len(df) == 3

    def test_empty_input_returns_empty_dataframe(self):
        # CDD-007
        df = build_decision_dashboard([])
        assert len(df) == 0

    def test_output_has_required_columns(self):
        # CDD-008
        results = [self._make_result("CUST-001", "PASS")]
        df = build_decision_dashboard(results)
        required = {"customer_id", "pass_or_reject", "confidence_level", "notes"}
        assert required.issubset(set(df.columns))
