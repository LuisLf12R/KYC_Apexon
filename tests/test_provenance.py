"""Tests for kyc_dashboard.provenance — Phase 11B."""

import pandas as pd
import pytest

from kyc_dashboard.provenance import (
    Discrepancy,
    ProvenanceRecord,
    ProvenanceStore,
    collect_discrepancies,
    record_ocr_provenance,
    update_customer_records,
)


class TestProvenanceStore:
    """PROV-001 through PROV-006."""

    def test_add_and_retrieve_single_record(self):
        # PROV-001
        store = ProvenanceStore()
        rec = ProvenanceRecord(
            customer_id="CUST-001",
            field_name="full_name",
            value="John Miller",
            source_type="OCR-Extracted",
            source_file="dl_front.png",
            confidence=0.95,
        )
        store.add_record(rec)
        result = store.get_records("CUST-001", "full_name")
        assert len(result) == 1
        assert result[0].value == "John Miller"

    def test_add_multiple_records_same_key(self):
        # PROV-002
        store = ProvenanceStore()
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "John", "User-Provided", "customers.csv"))
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "John A", "OCR-Extracted", "doc.png"))
        result = store.get_records("CUST-001", "full_name")
        assert len(result) == 2

    def test_get_records_with_field_filter(self):
        # PROV-003
        store = ProvenanceStore()
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "John", "User-Provided", "customers.csv"))
        store.add_record(ProvenanceRecord("CUST-001", "dob", "1985-07-22", "OCR-Extracted", "doc.png"))
        result = store.get_records("CUST-001", "dob")
        assert len(result) == 1
        assert result[0].field_name == "dob"

    def test_get_records_without_filter_returns_all_customer_fields(self):
        # PROV-004
        store = ProvenanceStore()
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "John", "User-Provided", "customers.csv"))
        store.add_record(ProvenanceRecord("CUST-001", "dob", "1985-07-22", "OCR-Extracted", "doc.png"))
        store.add_record(ProvenanceRecord("CUST-002", "full_name", "Ana", "User-Provided", "customers.csv"))
        result = store.get_records("CUST-001")
        assert len(result) == 2
        assert sorted([r.field_name for r in result]) == ["dob", "full_name"]

    def test_get_all_customers_sorted_unique(self):
        # PROV-005
        store = ProvenanceStore()
        store.add_record(ProvenanceRecord("CUST-002", "full_name", "Ana", "User-Provided", "customers.csv"))
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "John", "User-Provided", "customers.csv"))
        store.add_record(ProvenanceRecord("CUST-001", "dob", "1985-07-22", "OCR-Extracted", "doc.png"))
        assert store.get_all_customers() == ["CUST-001", "CUST-002"]

    def test_clear_empties_store(self):
        # PROV-006
        store = ProvenanceStore()
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "John", "User-Provided", "customers.csv"))
        store.clear()
        assert store.get_records("CUST-001") == []


class TestRecordOcrProvenance:
    """PROV-007 through PROV-009."""

    def test_creates_records_with_correct_attributes(self):
        # PROV-007
        store = ProvenanceStore()
        fields = {"full_name": "John Miller", "dob": "1985-07-22"}
        confs = {"full_name": 0.95, "dob": 0.90}
        records = record_ocr_provenance(store, "CUST-001", fields, "dl_front.png", confs)
        assert len(records) == 2
        assert all(r.source_type == "OCR-Extracted" for r in records)
        assert all(r.source_file == "dl_front.png" for r in records)

    def test_normalizes_percentage_confidence(self):
        # PROV-008
        store = ProvenanceStore()
        fields = {"full_name": "John Miller"}
        confs = {"full_name": 95}
        records = record_ocr_provenance(store, "CUST-001", fields, "dl.png", confs)
        assert records[0].confidence == 0.95

    def test_handles_missing_confidence(self):
        # PROV-009
        store = ProvenanceStore()
        records = record_ocr_provenance(store, "CUST-001", {"full_name": "John"}, "dl.png")
        assert len(records) == 1
        assert records[0].confidence is None


class TestCollectDiscrepancies:
    """PROV-010 through PROV-013."""

    def test_no_discrepancy_single_source(self):
        # PROV-010
        store = ProvenanceStore()
        store.add_record(
            ProvenanceRecord(
                customer_id="CUST-001",
                field_name="full_name",
                value="John Miller",
                source_type="User-Provided",
                source_file="customers.csv",
            )
        )
        result = collect_discrepancies(store, "CUST-001")
        assert len(result) == 0

    def test_detects_discrepancy(self):
        # PROV-011
        store = ProvenanceStore()
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "John Miller", "User-Provided", "customers.csv"))
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "John A. Miller", "OCR-Extracted", "dl.png", 0.95))
        result = collect_discrepancies(store, "CUST-001")
        assert len(result) == 1
        assert result[0].field_name == "full_name"

    def test_no_discrepancy_case_insensitive_same_value(self):
        # PROV-012
        store = ProvenanceStore()
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "John Miller", "User-Provided", "customers.csv"))
        store.add_record(ProvenanceRecord("CUST-001", "full_name", "  john miller  ", "OCR-Extracted", "dl.png", 0.95))
        result = collect_discrepancies(store, "CUST-001")
        assert result == []

    def test_returns_existing_and_new_values(self):
        # PROV-013
        store = ProvenanceStore()
        store.add_record(ProvenanceRecord("CUST-001", "dob", "1985-07-22", "User-Provided", "customers.csv"))
        store.add_record(ProvenanceRecord("CUST-001", "dob", "1985-07-23", "OCR-Extracted", "doc.png", 0.8))
        result = collect_discrepancies(store, "CUST-001")
        assert len(result) == 1
        item = result[0]
        assert isinstance(item, Discrepancy)
        assert item.existing_value == "1985-07-22"
        assert item.new_value == "1985-07-23"


class TestUpdateCustomerRecords:
    """PROV-014 through PROV-016."""

    @pytest.fixture
    def sample_dataframes(self):
        id_verifications = pd.DataFrame(
            {
                "customer_id": ["CUST-001"],
                "document_type": ["passport"],
                "document_number": ["P12345"],
                "issue_date": ["2020-01-01"],
                "expiry_date": ["2028-01-01"],
                "verification_date": ["2024-01-01"],
                "document_status": ["VERIFIED"],
            }
        )
        documents = pd.DataFrame(
            {
                "customer_id": ["CUST-001"],
                "document_type": ["utility_bill"],
                "issue_date": ["2024-01-01"],
                "expiry_date": ["2025-01-01"],
                "document_category": ["POA"],
            }
        )
        return {"id_verifications": id_verifications, "documents": documents}

    def test_id_document_upserts_into_id_verifications(self, sample_dataframes):
        # PROV-014
        result = update_customer_records(
            sample_dataframes,
            "CUST-002",
            "passport",
            {"document_number": "P99999", "issue_date": "2025-01-01", "expiry_date": "2030-01-01"},
        )
        id_df = result["id_verifications"]
        row = id_df[id_df["customer_id"] == "CUST-002"].iloc[0]
        assert row["document_type"] == "passport"
        assert row["document_number"] == "P99999"
        assert row["expiry_date"] == "2030-01-01"

    def test_utility_bill_upserts_into_documents(self, sample_dataframes):
        # PROV-015
        result = update_customer_records(
            sample_dataframes,
            "CUST-002",
            "utility_bill",
            {"issue_date": "2026-01-01", "expiry_date": "2026-07-01"},
        )
        docs_df = result["documents"]
        row = docs_df[docs_df["customer_id"] == "CUST-002"].iloc[0]
        assert row["document_type"] == "utility_bill"
        assert row["document_category"] == "POA"
        assert row["issue_date"] == "2026-01-01"

    def test_returns_copies_not_originals(self, sample_dataframes):
        # PROV-016
        original_id = id(sample_dataframes["id_verifications"])
        original_docs = id(sample_dataframes["documents"])
        result = update_customer_records(
            sample_dataframes,
            "CUST-002",
            "passport",
            {"document_number": "P99999", "expiry_date": "2030-01-01"},
        )
        assert id(result["id_verifications"]) != original_id
        assert id(result["documents"]) != original_docs
        assert len(sample_dataframes["id_verifications"]) == 1
        assert len(sample_dataframes["documents"]) == 1
