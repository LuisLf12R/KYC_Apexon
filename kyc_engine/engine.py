"""
kyc_engine.py
KYC Compliance Engine — 6 dimensions + disposition layer.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from kyc_engine.dimensions.account_activity import AccountActivityDimension
from kyc_engine.dimensions.aml_screening import AMLScreeningDimension
from kyc_engine.dimensions.beneficial_ownership import BeneficialOwnershipDimension
from kyc_engine.dimensions.data_quality import DataQualityDimension
from kyc_engine.dimensions.identity import IdentityVerificationDimension
from kyc_engine.dimensions.proof_of_address import ProofOfAddressDimension
from kyc_engine.ruleset import get_active_ruleset_version, load_ruleset


class KYCComplianceEngine:
    DIMENSION_WEIGHTS = {
        "aml_screening": 0.25,
        "identity_verification": 0.20,
        "account_activity": 0.15,
        "proof_of_address": 0.15,
        "beneficial_ownership": 0.15,
        "data_quality": 0.10,
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
        except FileNotFoundError:
            return pd.DataFrame()

    def _load_all_data(self, customer_id: str) -> dict:
        screening_df = self._load_df("screenings_clean.csv")
        identity_df = self._load_df("id_verifications_clean.csv")
        beneficial_df = self._load_df("beneficial_ownership_clean.csv")
        transactions_df = self._load_df("transactions_clean.csv")
        address_df = self._load_df("documents_clean.csv")
        customer_df = self._load_df("customers_clean.csv")

        return {
            "screening": screening_df,
            "identity": identity_df,
            "beneficial_ownership": beneficial_df,
            "transactions": transactions_df,
            "address": address_df,
            "customer": customer_df,
            "screenings": self.screenings,
            "id_verifications": self.id_verifications,
            "ubo": self.ubo,
            "transactions_df": transactions_df,
            "transactions": self.transactions,
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

    def evaluate_customer(self, customer_id: str) -> dict:
        data = self._load_all_data(customer_id)

        identity_result = self._dimensions["identity"].evaluate(customer_id, data)
        screening_result = self._dimensions["screening"].evaluate(customer_id, data)
        ubo_result = self._dimensions["beneficial_ownership"].evaluate(customer_id, data)
        txn_result = self._dimensions["transactions"].evaluate(customer_id, data)
        doc_result = self._dimensions["documents"].evaluate(customer_id, data)
        dq_result = self._dimensions["data_quality"].evaluate(customer_id, data)

        dimension_results = {
            "identity": identity_result,
            "screening": screening_result,
            "beneficial_ownership": ubo_result,
            "transactions": txn_result,
            "documents": doc_result,
            "data_quality": dq_result,
        }

        screening_row = self.screenings[self.screenings["customer_id"] == customer_id] if "customer_id" in self.screenings.columns else pd.DataFrame()
        if screening_row.empty:
            aml_status = "no_screening_data"
            aml_score = 30.0
            aml_finding = "No AML screening record on file — mandatory before onboarding"
        else:
            s = screening_row.iloc[0]
            screening_result_value = str(s.get("screening_result", "")).upper()
            hit_status = str(s.get("hit_status", "")).upper()
            if screening_result_value == "MATCH" and hit_status == "CONFIRMED":
                aml_status = "confirmed_match"
                aml_score = 0.0
                aml_finding = "CONFIRMED sanctions match — customer appears on restricted list"
            elif screening_result_value == "MATCH":
                aml_status = "match_requires_review"
                aml_score = 50.0
                aml_finding = "Sanctions match requires analyst investigation — not yet resolved"
            else:
                aml_status = "no_match"
                aml_score = 100.0
                aml_finding = "No match on sanctions lists — screening current"

        def score_from_result(result: dict, fallback_pass=80.0, fallback_fail=40.0) -> float:
            details = result.get("evaluation_details", {})
            if "data_quality_score" in details:
                return float(details.get("data_quality_score", fallback_pass if result.get("passed") else fallback_fail))
            return float(fallback_pass if result.get("passed") else fallback_fail)

        id_score = score_from_result(identity_result)
        act_score = score_from_result(txn_result)
        poa_score = score_from_result(doc_result)
        ubo_score = score_from_result(ubo_result)
        dq_score = score_from_result(dq_result)

        aml_details = {"status": aml_status, "finding": aml_finding}
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

        overall_score = round(
            aml_score * self.DIMENSION_WEIGHTS["aml_screening"]
            + id_score * self.DIMENSION_WEIGHTS["identity_verification"]
            + act_score * self.DIMENSION_WEIGHTS["account_activity"]
            + poa_score * self.DIMENSION_WEIGHTS["proof_of_address"]
            + ubo_score * self.DIMENSION_WEIGHTS["beneficial_ownership"]
            + dq_score * self.DIMENSION_WEIGHTS["data_quality"],
            1,
        )

        result = {
            "customer_id": customer_id,
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
            "evaluation_date": datetime.now().isoformat(),
            "dimension_results": dimension_results,
        }

        disposition_info = self.determine_disposition(result)
        if screening_row.empty:
            disposition_info["disposition"] = "REVIEW"
            disposition_info["triggered_reject_rules"] = []
            disposition_info["rationale"] = "No screening record available; escalated to manual review."
        result.update(disposition_info)
        result["overall_status"] = disposition_info["disposition"]
        return result

    def evaluate_batch(self, customer_ids: List[str]) -> pd.DataFrame:
        results = []
        for cid in customer_ids:
            try:
                results.append(self.evaluate_customer(cid))
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
