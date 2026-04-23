"""P9-A: End-to-end integration tests — full customer lifecycle."""
import csv
from pathlib import Path

import pandas as pd
import pytest

from kyc_engine.engine import KYCComplianceEngine
from kyc_engine.models import CustomerDecision, DispositionLevel
from kyc_engine.ruleset import reset_ruleset_cache, get_active_ruleset_version


# ── helpers ────────────────────────────────────────────────────────────────────

def _write_csv(path: Path, rows: list):
    """Write a list of dicts as a CSV file."""
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _build_data_dir(tmp_path: Path) -> Path:
    """Create temp dir with synthetic CSVs for five test customers."""
    d = tmp_path / "data"
    d.mkdir()

    # ---- customers_clean.csv ----
    customers = [
        {
            "customer_id": "CUST_PASS",
            "customer_name": "Alice Pass",
            "risk_rating": "LOW",
            "jurisdiction": "USA",
            "entity_type": "INDIVIDUAL",
            "sow_declared": "employment_income",
            "crs_self_cert_on_file": "Y",
            "fatca_status": "w9_on_file",
            "w8_w9_on_file": "Y",
        },
        {
            "customer_id": "CUST_REJECT",
            "customer_name": "Bob Reject",
            "risk_rating": "HIGH",
            "jurisdiction": "USA",
            "entity_type": "INDIVIDUAL",
            "sow_declared": "employment_income",
            "crs_self_cert_on_file": "Y",
            "fatca_status": "w9_on_file",
            "w8_w9_on_file": "Y",
        },
        {
            "customer_id": "CUST_REVIEW_AML",
            "customer_name": "Carol Review",
            "risk_rating": "MEDIUM",
            "jurisdiction": "GBR",
            "entity_type": "INDIVIDUAL",
            "sow_declared": "employment_income",
            "crs_self_cert_on_file": "Y",
            "fatca_status": "",
            "w8_w9_on_file": "",
        },
        {
            "customer_id": "CUST_NO_SCREEN",
            "customer_name": "Dave NoScreen",
            "risk_rating": "LOW",
            "jurisdiction": "USA",
            "entity_type": "INDIVIDUAL",
            "sow_declared": "employment_income",
            "crs_self_cert_on_file": "Y",
            "fatca_status": "w9_on_file",
            "w8_w9_on_file": "Y",
        },
        {
            "customer_id": "CUST_CRS_MISS",
            "customer_name": "Eve CRS",
            "risk_rating": "LOW",
            "jurisdiction": "GBR",
            "entity_type": "INDIVIDUAL",
            "sow_declared": "employment_income",
            "crs_self_cert_on_file": "N",
            "fatca_status": "",
            "w8_w9_on_file": "",
        },
    ]
    _write_csv(d / "customers_clean.csv", customers)

    # ---- screenings_clean.csv ----
    screenings = [
        {
            "customer_id": "CUST_PASS",
            "screening_date": "2026-01-15",
            "screening_result": "NO_HIT",
            "resolution_status": "",
            "resolution_date": "",
            "match_name": "",
            "match_score": "",
            "list_reference": "OFAC_SDN",
        },
        {
            "customer_id": "CUST_REJECT",
            "screening_date": "2026-01-15",
            "screening_result": "EXACT_MATCH",
            "resolution_status": "RESOLVED_BLOCKED",
            "resolution_date": "2026-01-20",
            "match_name": "Bob BadActor",
            "match_score": "0.99",
            "list_reference": "OFAC_SDN",
        },
        {
            "customer_id": "CUST_REVIEW_AML",
            "screening_date": "2026-01-15",
            "screening_result": "FUZZY_MATCH",
            "resolution_status": "UNRESOLVED",
            "resolution_date": "",
            "match_name": "Carol Similar",
            "match_score": "0.87",
            "list_reference": "OFSI_CONS",
        },
        # CUST_NO_SCREEN intentionally has no screening rows
        {
            "customer_id": "CUST_CRS_MISS",
            "screening_date": "2026-01-15",
            "screening_result": "NO_HIT",
            "resolution_status": "",
            "resolution_date": "",
            "match_name": "",
            "match_score": "",
            "list_reference": "OFAC_SDN",
        },
    ]
    _write_csv(d / "screenings_clean.csv", screenings)

    # ---- id_verifications_clean.csv ----
    id_vers = []
    for cid, cname in [
        ("CUST_PASS", "Alice Pass"),
        ("CUST_REJECT", "Bob Reject"),
        ("CUST_REVIEW_AML", "Carol Review"),
        ("CUST_NO_SCREEN", "Dave NoScreen"),
        ("CUST_CRS_MISS", "Eve CRS"),
    ]:
        id_vers.append({
            "customer_id": cid,
            "document_type": "PASSPORT",
            "expiry_date": "2028-06-01",
            "verification_date": "2026-01-10",
            "verification_method": "electronic",
            "name_on_document": cname,
        })
    _write_csv(d / "id_verifications_clean.csv", id_vers)

    # ---- transactions_clean.csv (minimal — only CUST_PASS) ----
    _write_csv(d / "transactions_clean.csv", [
        {
            "customer_id": "CUST_PASS",
            "transaction_date": "2026-01-15",
            "amount": "5000",
            "currency": "USD",
            "transaction_type": "wire_transfer",
        },
    ])

    # ---- documents_clean.csv (SoW evidence + PoA for CUST_PASS) ----
    _write_csv(d / "documents_clean.csv", [
        {
            "customer_id": "CUST_PASS",
            "document_category": "SOW",
            "issue_date": "2026-01-01",
            "document_type": "bank_statement",
            "expiry_date": "",
        },
        {
            "customer_id": "CUST_PASS",
            "document_category": "POA",
            "issue_date": "2026-01-01",
            "document_type": "utility_bill",
            "expiry_date": "",
        },
    ])

    # ---- beneficial_ownership_clean.csv (minimal for CUST_PASS) ----
    _write_csv(d / "beneficial_ownership_clean.csv", [
        {
            "customer_id": "CUST_PASS",
            "owner_name": "Alice Pass",
            "ownership_pct": "100",
            "is_individual": "True",
        },
    ])

    return d


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="class")
def engine_and_results(tmp_path_factory):
    """Build engine once from synthetic data; evaluate all five customers."""
    reset_ruleset_cache()
    data_dir = _build_data_dir(tmp_path_factory.mktemp("e2e"))
    engine = KYCComplianceEngine(data_clean_dir=data_dir)

    results = {}
    for cid in [
        "CUST_PASS",
        "CUST_REJECT",
        "CUST_REVIEW_AML",
        "CUST_NO_SCREEN",
        "CUST_CRS_MISS",
    ]:
        results[cid] = engine.evaluate_customer(cid)

    batch_df = engine.evaluate_batch(
        ["CUST_PASS", "CUST_REJECT", "CUST_REVIEW_AML", "CUST_NO_SCREEN", "CUST_CRS_MISS"]
    )

    yield engine, results, batch_df

    # Teardown — allow other test modules to reload the real ruleset
    reset_ruleset_cache()


# ── tests ──────────────────────────────────────────────────────────────────────

class TestIntegrationE2E:
    """End-to-end integration tests across full evaluate_customer lifecycle."""

    # -- E2E-001: engine loads and evaluates without error --------

    def test_e2e_001_all_customers_evaluated(self, engine_and_results):
        """E2E-001: Engine evaluates all five synthetic customers without error."""
        _, results, _ = engine_and_results
        assert len(results) == 5
        for cid, result in results.items():
            assert "disposition" in result, f"{cid} missing disposition"
            assert "overall_score" in result, f"{cid} missing overall_score"

    # -- E2E-002: output validates against CustomerDecision --------

    def test_e2e_002_customer_decision_validates(self, engine_and_results):
        """E2E-002: Every result passes CustomerDecision.model_validate()."""
        _, results, _ = engine_and_results
        for cid, result in results.items():
            validated = CustomerDecision.model_validate(result)
            assert validated.customer_id == cid

    # -- E2E-003: ruleset version present and correct --------

    def test_e2e_003_ruleset_version_in_output(self, engine_and_results):
        """E2E-003: ruleset_version field matches active ruleset version."""
        engine, results, _ = engine_and_results
        expected = engine.ruleset_version
        for cid, result in results.items():
            assert result["ruleset_version"] == expected, (
                f"{cid}: expected {expected}, got {result['ruleset_version']}"
            )

    # -- E2E-004: confirmed sanctions → REJECT with HR-001 --------

    def test_e2e_004_confirmed_sanctions_reject(self, engine_and_results):
        """E2E-004: RESOLVED_BLOCKED screening → REJECT via HR-001."""
        _, results, _ = engine_and_results
        r = results["CUST_REJECT"]
        assert r["disposition"] == "REJECT"
        reject_ids = [tr["rule_id"] for tr in r["triggered_reject_rules"]]
        assert "HR-001" in reject_ids

    # -- E2E-005: unresolved AML match → REVIEW with RV-001 --------

    def test_e2e_005_unresolved_match_review(self, engine_and_results):
        """E2E-005: UNRESOLVED screening hit → REVIEW via RV-001."""
        _, results, _ = engine_and_results
        r = results["CUST_REVIEW_AML"]
        assert r["disposition"] == "REVIEW"
        review_ids = [tr["rule_id"] for tr in r["triggered_review_rules"]]
        assert "RV-001" in review_ids

    # -- E2E-006: no screening data → REVIEW (engine override) --------

    def test_e2e_006_no_screening_review(self, engine_and_results):
        """E2E-006: Customer with no screening records → REVIEW override."""
        _, results, _ = engine_and_results
        r = results["CUST_NO_SCREEN"]
        assert r["disposition"] == "REVIEW"
        assert "no screening" in r["rationale"].lower()

    # -- E2E-007: CRS cert missing → triggers RV-CRS-001 --------

    def test_e2e_007_crs_cert_missing_review(self, engine_and_results):
        """E2E-007: CRS jurisdiction + cert missing → RV-CRS-001 triggered."""
        _, results, _ = engine_and_results
        r = results["CUST_CRS_MISS"]
        assert r["disposition"] == "REVIEW"
        review_ids = [tr["rule_id"] for tr in r["triggered_review_rules"]]
        assert "RV-CRS-001" in review_ids

    # -- E2E-008: batch returns DataFrame with expected columns --------

    def test_e2e_008_batch_returns_dataframe(self, engine_and_results):
        """E2E-008: evaluate_batch returns a DataFrame with core columns."""
        _, _, batch_df = engine_and_results
        assert isinstance(batch_df, pd.DataFrame)
        assert len(batch_df) == 5
        for col in ["customer_id", "disposition", "overall_score", "ruleset_version"]:
            assert col in batch_df.columns, f"batch missing column: {col}"

    # -- E2E-009: batch sorts REJECT before REVIEW before PASS --------

    def test_e2e_009_batch_disposition_ordering(self, engine_and_results):
        """E2E-009: Batch DataFrame is sorted by disposition severity."""
        _, _, batch_df = engine_and_results
        order_map = {"REJECT": 0, "REVIEW": 1, "PASS_WITH_NOTES": 2, "PASS": 3}
        severity_seq = [order_map.get(d, 4) for d in batch_df["disposition"]]
        assert severity_seq == sorted(severity_seq), (
            f"Batch not sorted by severity: {list(batch_df['disposition'])}"
        )

    # -- E2E-010: all expected fields present in output --------

    def test_e2e_010_all_expected_fields_present(self, engine_and_results):
        """E2E-010: Full output dict contains every expected field."""
        _, results, _ = engine_and_results
        expected_fields = {
            "customer_id",
            "jurisdiction",
            "overall_score",
            "aml_screening_score",
            "aml_screening_details",
            "identity_verification_score",
            "identity_verification_details",
            "account_activity_score",
            "account_activity_details",
            "proof_of_address_score",
            "proof_of_address_details",
            "beneficial_ownership_score",
            "beneficial_ownership_details",
            "data_quality_score",
            "data_quality_details",
            "source_of_wealth_score",
            "source_of_wealth_details",
            "crs_fatca_score",
            "crs_fatca_details",
            "disposition",
            "overall_status",
            "triggered_reject_rules",
            "triggered_review_rules",
            "rationale",
            "ruleset_version",
            "evaluation_date",
            "dimension_results",
        }
        for cid, result in results.items():
            missing = expected_fields - set(result.keys())
            assert not missing, f"{cid} missing fields: {missing}"
