"""
kyc_engine.py
KYC Compliance Engine — 6 dimensions + disposition layer.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from kyc_engine.models import CustomerDecision
from kyc_engine.dimensions.crs_fatca import CRSFATCADimension
from kyc_engine.dimensions.source_of_wealth import SourceOfWealthDimension
from kyc_engine.dimensions.account_activity import AccountActivityDimension
from kyc_engine.dimensions.aml_screening import AMLScreeningDimension
from kyc_engine.dimensions.beneficial_ownership import BeneficialOwnershipDimension
from kyc_engine.dimensions.data_quality import DataQualityDimension
from kyc_engine.dimensions.identity import IdentityVerificationDimension
from kyc_engine.dimensions.proof_of_address import ProofOfAddressDimension
from kyc_engine.ruleset import (
    get_active_ruleset_version,
    get_institution_params,
    get_jurisdiction_params,
    load_ruleset,
)


class KYCComplianceEngine:
    DIMENSION_WEIGHTS = {
        "aml_screening": 0.25,
        "identity_verification": 0.20,
        "account_activity": 0.15,
        "proof_of_address": 0.10,
        "beneficial_ownership": 0.15,
        "data_quality": 0.05,
        "source_of_wealth": 0.08,
        "crs_fatca": 0.02,
    }

    DISPOSITION_ORDER = {"REJECT": 0, "REVIEW": 1, "PASS_WITH_NOTES": 2, "PASS": 3}

    def __init__(self, data_clean_dir: Path = None):
        self.data_clean_dir = data_clean_dir or Path.cwd() / "Data Clean"
        self._manifest = load_ruleset()
        self.ruleset = self._manifest.model_dump()
        self.ruleset_version = get_active_ruleset_version()

        self.customers = self._load_df("customers_clean.csv")
        self.screenings = self._load_df("screenings_clean.csv")
        self.id_verifications = self._load_df("id_verifications_clean.csv")
        self.transactions = self._load_df("transactions_clean.csv")
        self.documents = self._load_df("documents_clean.csv")
        self.beneficial_owners = self._load_df("beneficial_ownership_clean.csv")
        self.ubo = self.beneficial_owners

        p = self._manifest.dimension_parameters
        self._dimensions = {
            "identity": IdentityVerificationDimension(p.identity),
            "screening": AMLScreeningDimension(p.screening),
            "beneficial_ownership": BeneficialOwnershipDimension(p.beneficial_ownership),
            "transactions": AccountActivityDimension(p.transactions),
            "documents": ProofOfAddressDimension(p.documents),
            "data_quality": DataQualityDimension(p.data_quality),
        }

    def _load_df(self, filename: str) -> pd.DataFrame:
        try:
            return pd.read_csv(self.data_clean_dir / filename)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            return pd.DataFrame()

    def _load_all_data(self, customer_id: str) -> dict:
        # P7-A/D: use pre-loaded instance attributes — no per-call disk reads.
        # All keys are aliases over the same DataFrames loaded at __init__ time.
        return {
            "screening": self.screenings,
            "identity": self.id_verifications,
            "beneficial_ownership": self.beneficial_owners,
            "transactions": self.transactions,
            "address": self.documents,
            "customer": self.customers,
            "screenings": self.screenings,
            "id_verifications": self.id_verifications,
            "ubo": self.ubo,
            "transactions_df": self.transactions,
            "documents": self.documents,
            "customers": self.customers,
        }

    def determine_disposition(self, dimension_results: dict) -> dict:
        triggered_rejects = []
        triggered_reviews = []

        def matches(rule: dict) -> bool:
            dim = rule["dimension"]
            field = rule["condition_field"]
            value = rule["condition_value"]
            details = dimension_results.get(f"{dim}_details", {})
            return str(details.get(field, "")).strip().lower() == str(value).strip().lower()

        for rule in self.ruleset.get("hard_reject_rules", []):
            if matches(rule):
                triggered_rejects.append(
                    {
                        "rule_id": rule["rule_id"],
                        "name": rule["name"],
                        "description": rule["description"],
                        "policy_reference": rule.get("policy_reference", ""),
                        "dimension": rule["dimension"],
                    }
                )

        for rule in self.ruleset.get("review_rules", []):
            if matches(rule):
                triggered_reviews.append(
                    {
                        "rule_id": rule["rule_id"],
                        "name": rule["name"],
                        "description": rule["description"],
                        "policy_reference": rule.get("policy_reference", ""),
                        "dimension": rule["dimension"],
                    }
                )

        thresholds = self.ruleset.get("score_thresholds", {})
        pass_min = thresholds.get("pass_minimum", 70)
        notes_min = thresholds.get("pass_with_notes_minimum", 50)
        score = dimension_results.get("overall_score", 0)

        if triggered_rejects:
            disposition = "REJECT"
            rationale = (
                f"Hard rejection triggered by {len(triggered_rejects)} rule(s). "
                f"Score of {score}/100 is noted for context but does not affect this disposition. "
                f"Triggered: {', '.join(r['rule_id'] for r in triggered_rejects)}."
            )
        elif triggered_reviews:
            disposition = "REVIEW"
            rationale = (
                f"Manual review required — {len(triggered_reviews)} rule(s) triggered. "
                f"Score: {score}/100. "
                f"Triggered: {', '.join(r['rule_id'] for r in triggered_reviews)}."
            )
        elif score >= pass_min:
            disposition = "PASS"
            rationale = (
                f"No reject or review triggers. Score {score}/100 meets the "
                f"{pass_min}-point pass threshold."
            )
        elif score >= notes_min:
            disposition = "PASS_WITH_NOTES"
            rationale = (
                f"No reject or review triggers, but score {score}/100 is below the "
                f"{pass_min}-point pass threshold. Proceed with documented caveats."
            )
        else:
            disposition = "REVIEW"
            rationale = (
                f"Score {score}/100 falls below the minimum acceptable threshold of "
                f"{notes_min}. Escalated to manual review."
            )
            triggered_reviews.append(
                {
                    "rule_id": "RV-SCORE",
                    "name": "Score Below Minimum Threshold",
                    "description": f"Weighted score {score} is below the {notes_min}-point floor.",
                    "policy_reference": "Scoring Policy 1.1",
                    "dimension": "composite",
                }
            )

        return {
            "disposition": disposition,
            "triggered_reject_rules": triggered_rejects,
            "triggered_review_rules": triggered_reviews,
            "rationale": rationale,
            "ruleset_version": self.ruleset_version,
        }

    def evaluate_customer(self, customer_id: str, institution_id: str = None) -> dict:
        data = self._load_all_data(customer_id)

        customer_row = (
            data["customers"][data["customers"]["customer_id"] == customer_id]
            if data.get("customers") is not None and "customer_id" in data["customers"].columns
            else pd.DataFrame()
        )

        # Resolve jurisdiction and fetch merged params for this customer
        jurisdiction = None
        if data.get("customers") is not None:
            cust_df = data["customers"]
            cust_row = cust_df[cust_df["customer_id"] == customer_id]
            if not cust_row.empty and "jurisdiction" in cust_row.columns:
                jurisdiction = str(cust_row.iloc[0]["jurisdiction"]).strip()

        jurisdiction_code = jurisdiction if jurisdiction else "UNKNOWN"
        if institution_id is not None:
            merged_params = get_institution_params(jurisdiction_code, institution_id)
        else:
            merged_params = get_jurisdiction_params(jurisdiction_code)

        screening_cfg = merged_params.get("screening", {})
        aml_params = self._manifest.dimension_parameters.screening.__class__(
            max_screening_age_days=screening_cfg.get("max_screening_age_days", 365),
            fuzzy_match_threshold=screening_cfg.get("fuzzy_match_threshold", 0.85),
        )

        identity_cfg = merged_params.get("identity", {})
        identity_params = self._manifest.dimension_parameters.identity.__class__(
            min_verified_docs=identity_cfg.get("min_verified_docs", 1),
            doc_expiry_warning_days=identity_cfg.get("doc_expiry_warning_days", 90),
            accepted_doc_types=identity_cfg.get("accepted_doc_types", ["passport"]),
        )

        ubo_cfg = merged_params.get("beneficial_ownership", {})
        ubo_params = self._manifest.dimension_parameters.beneficial_ownership.__class__(
            ownership_threshold_pct=ubo_cfg.get("ownership_threshold_pct", 25.0),
            max_chain_depth=ubo_cfg.get("max_chain_depth", 4),
        )

        tx_cfg = merged_params.get("transactions", {})
        tx_params = self._manifest.dimension_parameters.transactions.__class__(
            edd_trigger_threshold_usd=tx_cfg.get("edd_trigger_threshold_usd", 10000.0),
            velocity_window_days=tx_cfg.get("velocity_window_days", 90),
        )

        doc_cfg = merged_params.get("documents", {})
        doc_params = self._manifest.dimension_parameters.documents.__class__(
            max_doc_age_days=doc_cfg.get("max_doc_age_days", 90),
            accepted_proof_of_address_types=doc_cfg.get(
                "accepted_proof_of_address_types", ["utility_bill"]
            ),
        )

        dq_cfg = merged_params.get("data_quality", {})
        dq_params = self._manifest.dimension_parameters.data_quality.__class__(
            critical_fields=dq_cfg.get("critical_fields", ["customer_id"]),
            poor_quality_threshold=dq_cfg.get("poor_quality_threshold", 0.2),
        )

        sow_cfg = merged_params.get("source_of_wealth", {})
        sow_params = self._manifest.dimension_parameters.source_of_wealth.__class__(
            accepted_sow_categories=sow_cfg.get(
                "accepted_sow_categories", ["employment_income", "inheritance"]
            ),
            min_evidence_docs=sow_cfg.get("min_evidence_docs", 1),
            max_evidence_age_days=sow_cfg.get("max_evidence_age_days", 365),
        )
        crs_cfg = merged_params.get("crs_fatca", {})
        crs_params = self._manifest.dimension_parameters.crs_fatca.__class__(
            fatca_applicable_jurisdictions=crs_cfg.get(
                "fatca_applicable_jurisdictions", ["USA"]
            ),
            crs_participating_jurisdictions=crs_cfg.get(
                "crs_participating_jurisdictions",
                ["GBR", "EU", "CHE", "SGP", "HKG", "AUS", "CAN", "UAE", "IND"],
            ),
            w8_w9_required_entity_types=crs_cfg.get(
                "w8_w9_required_entity_types", ["INDIVIDUAL", "LEGAL_ENTITY"]
            ),
        )

        identity_result = IdentityVerificationDimension(identity_params).evaluate(customer_id, data)
        screening_result = AMLScreeningDimension(aml_params).evaluate(customer_id, data)
        ubo_result = BeneficialOwnershipDimension(ubo_params).evaluate(customer_id, data)
        txn_result = AccountActivityDimension(tx_params).evaluate(customer_id, data)
        doc_result = ProofOfAddressDimension(doc_params).evaluate(customer_id, data)
        dq_result = DataQualityDimension(dq_params).evaluate(customer_id, data)
        sow_result = SourceOfWealthDimension(sow_params).evaluate(customer_id, data)
        crs_result = CRSFATCADimension(crs_params).evaluate(customer_id, data)

        dimension_results = {
            "identity": identity_result,
            "screening": screening_result,
            "beneficial_ownership": ubo_result,
            "transactions": txn_result,
            "documents": doc_result,
            "data_quality": dq_result,
            "source_of_wealth": sow_result,
            "crs_fatca": crs_result,
        }

        def _extract_score(
            result: dict,
            fallback_pass: int = 80,
            fallback_fail: int = 40,
        ) -> int:
            """
            Extract the actual computed score from a dimension result dict.
            Falls back to pass/fail approximation only when no score key present.
            """
            if "score" in result and result["score"] is not None:
                return int(result["score"])
            return fallback_pass if result.get("passed") else fallback_fail

        # P7-A: AML score and status are now sourced from AMLScreeningDimension
        aml_score = float(_extract_score(screening_result))
        aml_status = screening_result.get("aml_status", "no_screening_data")
        aml_hit_status = screening_result.get("aml_hit_status", "")
        aml_finding = "; ".join(screening_result.get("findings", [])[:2])

        id_score = _extract_score(identity_result)
        act_score = _extract_score(txn_result)
        poa_score = _extract_score(doc_result)
        ubo_score = _extract_score(ubo_result)
        dq_score = _extract_score(dq_result)

        aml_details = {"status": aml_status, "hit_status": aml_hit_status, "finding": aml_finding}
        id_details = {
            "status": "verified" if identity_result.get("passed") else "no_documents",
            "finding": "; ".join(identity_result.get("findings", [])[:2]),
        }
        act_details = {
            "status": "activity_assessed" if txn_result.get("passed") else "no_activity",
            "finding": "; ".join(txn_result.get("findings", [])[:2]),
        }
        poa_details = {
            "status": "address_on_file" if doc_result.get("passed") else "address_incomplete",
            "finding": "; ".join(doc_result.get("findings", [])[:2]),
        }
        ubo_details = {
            "status": "ubo_identified" if ubo_result.get("passed") else "no_ubo_record",
            "finding": "; ".join(ubo_result.get("findings", [])[:2]),
        }
        dq_details = {
            "status": "data_quality",
            "quality_rating": "Good" if dq_result.get("passed") else "Poor",
            "finding": "; ".join(dq_result.get("findings", [])[:2]),
        }
        sow_score = float(_extract_score(sow_result))
        sow_details = {
            "status": sow_result.get("sow_status", "sow_not_declared"),
            "finding": "; ".join(sow_result.get("findings", [])[:2]),
        }
        crs_score = float(_extract_score(crs_result))
        crs_details = {
            "status": crs_result.get("crs_fatca_status", "not_applicable"),
            "finding": "; ".join(crs_result.get("findings", [])[:2]),
        }

        overall_score = round(
            aml_score * self.DIMENSION_WEIGHTS["aml_screening"]
            + id_score * self.DIMENSION_WEIGHTS["identity_verification"]
            + act_score * self.DIMENSION_WEIGHTS["account_activity"]
            + poa_score * self.DIMENSION_WEIGHTS["proof_of_address"]
            + ubo_score * self.DIMENSION_WEIGHTS["beneficial_ownership"]
            + dq_score * self.DIMENSION_WEIGHTS["data_quality"]
            + sow_score * self.DIMENSION_WEIGHTS["source_of_wealth"]
            + crs_score * self.DIMENSION_WEIGHTS["crs_fatca"],
            1,
        )

        result = {
            "customer_id": customer_id,
            "jurisdiction": jurisdiction_code,
            "overall_score": overall_score,
            "aml_screening_score": round(aml_score, 1),
            "aml_screening_details": aml_details,
            "identity_verification_score": round(id_score, 1),
            "identity_verification_details": id_details,
            "account_activity_score": round(act_score, 1),
            "account_activity_details": act_details,
            "proof_of_address_score": round(poa_score, 1),
            "proof_of_address_details": poa_details,
            "beneficial_ownership_score": round(ubo_score, 1),
            "beneficial_ownership_details": ubo_details,
            "data_quality_score": round(dq_score, 1),
            "data_quality_details": dq_details,
            "source_of_wealth_score": round(sow_score, 1),
            "source_of_wealth_details": sow_details,
            "crs_fatca_score": round(crs_score, 1),
            "crs_fatca_details": crs_details,
            "evaluation_date": datetime.now().isoformat(),
            "dimension_results": dimension_results,
        }

        disposition_info = self.determine_disposition(result)
        if aml_status == "no_screening_data":
            disposition_info["disposition"] = "REVIEW"
            disposition_info["triggered_reject_rules"] = []
            disposition_info["rationale"] = "No screening record available; escalated to manual review."
        result.update(disposition_info)
        result["overall_status"] = disposition_info["disposition"]
        # P7-C: validate through CustomerDecision — surfaces field drift at
        # evaluation time rather than silently downstream.
        try:
            validated = CustomerDecision.model_validate(result)
            return validated.model_dump(mode="json")
        except Exception as exc:  # pragma: no cover — schema drift is a bug
            import logging
            logging.getLogger(__name__).error(
                "CustomerDecision validation failed for %s: %s", customer_id, exc
            )
            return result

    def evaluate_batch(self, customer_ids: List[str], institution_id: str = None) -> pd.DataFrame:
        results = []
        for cid in customer_ids:
            try:
                results.append(self.evaluate_customer(cid, institution_id=institution_id))
            except Exception:
                pass

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        score_cols = [
            "customer_id",
            "overall_score",
            "disposition",
            "aml_screening_score",
            "identity_verification_score",
            "account_activity_score",
            "proof_of_address_score",
            "beneficial_ownership_score",
            "data_quality_score",
            "rationale",
            "ruleset_version",
        ]
        df = df[[c for c in score_cols if c in df.columns]]

        order = {"REJECT": 0, "REVIEW": 1, "PASS_WITH_NOTES": 2, "PASS": 3}
        df["_sort"] = df["disposition"].map(order).fillna(4)
        df = df.sort_values(["_sort", "overall_score"]).drop(columns=["_sort"])

        return df
