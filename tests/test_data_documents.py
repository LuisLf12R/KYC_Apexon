"""Tests for the unified Data & Documents tab — Phase 11C."""

import pandas as pd
import pytest

from kyc_dashboard.tabs.data_documents import _classify_file, _fuzzy_match_customer


class TestClassifyFile:
    """DD-001 through DD-004."""

    def test_csv_is_structured(self):
        # DD-001
        assert _classify_file("customers.csv") == "structured"
        assert _classify_file("DATA.XLSX") == "structured"
        assert _classify_file("records.json") == "structured"

    def test_pdf_is_document(self):
        # DD-002
        assert _classify_file("license.pdf") == "document"
        assert _classify_file("SCAN.PNG") == "document"
        assert _classify_file("report.docx") == "document"

    def test_image_types_are_document(self):
        # DD-003
        assert _classify_file("photo.jpg") == "document"
        assert _classify_file("photo.jpeg") == "document"
        assert _classify_file("scan.tiff") == "document"

    def test_unknown_type(self):
        # DD-004
        assert _classify_file("readme.txt") == "unknown"
        assert _classify_file("data.xml") == "unknown"


class TestFuzzyMatchCustomer:
    """DD-005 through DD-011."""

    @pytest.fixture
    def customers_df(self):
        return pd.DataFrame(
            {
                "customer_id": ["CUST-001", "CUST-002", "CUST-003", "CUST-004"],
                "full_name": ["John A. Miller", "Sarah Chen", "Dmitri Volkov", "John Miller Jr"],
                "date_of_birth": ["1985-07-22", "1990-03-15", "1978-11-30", "2010-01-01"],
            }
        )

    def test_exact_match_returns_high_score(self, customers_df):
        # DD-005
        matches = _fuzzy_match_customer("John A. Miller", None, customers_df)
        assert len(matches) >= 1
        assert matches[0][0] == "CUST-001"
        assert matches[0][2] > 0.95

    def test_close_match_returns_above_threshold(self, customers_df):
        # DD-006
        matches = _fuzzy_match_customer("John Miller", None, customers_df)
        assert len(matches) >= 1
        cids = [m[0] for m in matches]
        assert "CUST-001" in cids

    def test_no_match_below_threshold(self, customers_df):
        # DD-007
        matches = _fuzzy_match_customer("Xavier Unknown", None, customers_df)
        assert len(matches) == 0

    def test_dob_boosts_score(self, customers_df):
        # DD-008
        matches_no_dob = _fuzzy_match_customer("John Miller", None, customers_df, threshold=0.5)
        matches_with_dob = _fuzzy_match_customer("John Miller", "1985-07-22", customers_df, threshold=0.5)
        score_no_dob = next((m[2] for m in matches_no_dob if m[0] == "CUST-001"), 0)
        score_with_dob = next((m[2] for m in matches_with_dob if m[0] == "CUST-001"), 0)
        assert score_with_dob >= score_no_dob

    def test_empty_name_returns_empty(self, customers_df):
        # DD-009
        assert _fuzzy_match_customer("", None, customers_df) == []
        assert _fuzzy_match_customer(None, None, customers_df) == []

    def test_empty_dataframe_returns_empty(self):
        # DD-010
        empty_df = pd.DataFrame(columns=["customer_id", "full_name"])
        assert _fuzzy_match_customer("John Miller", None, empty_df) == []

    def test_results_sorted_by_score_descending(self, customers_df):
        # DD-011
        matches = _fuzzy_match_customer("John Miller", None, customers_df, threshold=0.5)
        if len(matches) > 1:
            scores = [m[2] for m in matches]
            assert scores == sorted(scores, reverse=True)
