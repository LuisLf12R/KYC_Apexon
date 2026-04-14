"""
kyc_engine.py
KYC Compliance Engine — 6 dimensions + disposition layer.

Architecture:
    1. Evaluate each of the 6 weighted dimensions → score (0–100)
    2. Compute weighted overall score
    3. Run disposition engine against versioned rules:
       - Hard Reject triggers → REJECT (score cannot override)
       - Review triggers      → REVIEW (hold for human decision)
       - Score thresholds     → PASS / PASS_WITH_NOTES
    4. Return full result: score + disposition + triggered rules + rationale

Disposition controls final outcome.
Score explains relative strength within and across dispositions.
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional


# ── Ruleset loader ────────────────────────────────────────────────────────────

def load_ruleset(rules_path: Path = None) -> dict:
    """Load versioned rules from rules/kyc_rules_v1.0.json."""
    if rules_path is None:
        rules_path = Path.cwd() / "rules" / "kyc_rules_v1.0.json"
    try:
        if rules_path.exists():
            with open(rules_path) as f:
                return json.load(f)
    except Exception:
        pass
    # Fallback minimal ruleset if file missing
    return {
        "version": "kyc-rules-fallback",
        "hard_reject_rules": [],
        "review_rules": [],
        "score_thresholds": {"pass_minimum": 70, "pass_with_notes_minimum": 50}
    }


RULESET = load_ruleset()


class KYCComplianceEngine:
    """
    Unified KYC compliance evaluation engine.

    Evaluates customers across 6 dimensions, computes a weighted score,
    then applies a disposition layer (REJECT / REVIEW / PASS_WITH_NOTES / PASS)
    based on a versioned ruleset. Disposition controls final outcome;
    score explains relative strength.
    """

    DIMENSION_WEIGHTS = {
        "aml_screening":         0.25,
        "identity_verification": 0.20,
        "account_activity":      0.15,
        "proof_of_address":      0.15,
        "beneficial_ownership":  0.15,
        "data_quality":          0.10,
    }

    DISPOSITION_ORDER = {"REJECT": 0, "REVIEW": 1, "PASS_WITH_NOTES": 2, "PASS": 3}

    def __init__(self, data_clean_dir: Path = None):
        self.data_clean_dir = data_clean_dir or Path.cwd() / "Data Clean"
        self.ruleset = RULESET
        self.ruleset_version = RULESET.get("version", "unknown")

        self.customers        = self._load_df("customers_clean.csv")
        self.screenings       = self._load_df("screenings_clean.csv")
        self.id_verifications = self._load_df("id_verifications_clean.csv")
        self.transactions     = self._load_df("transactions_clean.csv")
        self.beneficial_owners = self._load_df("beneficial_ownership_clean.csv")

    def _load_df(self, filename: str) -> pd.DataFrame:
        try:
            return pd.read_csv(self.data_clean_dir / filename)
        except FileNotFoundError:
            return pd.DataFrame()

    # =========================================================================
    # DIMENSION 1: AML SCREENING (25%)
    # =========================================================================

    def evaluate_aml_screening(self, customer_id: str) -> Tuple[float, Dict]:
        if self.screenings is None or len(self.screenings) == 0:
            return 30, {"status": "no_screening_data",
                        "finding": "No screening records available"}

        screening = self.screenings[self.screenings["customer_id"] == customer_id]

        if len(screening) == 0:
            return 30, {"status": "no_screening_record",
                        "finding": "No AML screening record on file — mandatory before onboarding"}

        s = screening.iloc[0]
        result = s["screening_result"]
        hit_status = s.get("hit_status")

        if result == "NO_MATCH":
            try:
                days_ago = (datetime.now() - pd.to_datetime(s["screening_date"])).days
                if days_ago <= 90:
                    return 100, {"status": "no_match",
                                 "list_reference": s.get("list_reference", "N/A"),
                                 "finding": "No match on sanctions lists — screening current"}
                elif days_ago <= 180:
                    return 85, {"status": "no_match",
                                "days_since_screening": days_ago,
                                "finding": f"No match on sanctions lists — screening {days_ago} days old"}
                else:
                    return 70, {"status": "stale_screening",
                                "days_since_screening": days_ago,
                                "finding": f"Screening is {days_ago} days old — exceeds 180-day refresh requirement"}
            except Exception:
                return 80, {"status": "no_match", "finding": "No match on sanctions lists"}

        elif result == "MATCH":
            if hit_status == "FALSE_POSITIVE":
                return 70, {"status": "false_positive",
                             "match_name": s.get("match_name"),
                             "list_reference": s.get("list_reference"),
                             "finding": "Match resolved as false positive — name similarity only"}
            elif hit_status == "CONFIRMED":
                return 0, {"status": "confirmed_match",
                            "match_name": s.get("match_name"),
                            "list_reference": s.get("list_reference"),
                            "finding": "CONFIRMED sanctions match — customer appears on restricted list"}
            else:
                return 50, {"status": "match_requires_review",
                             "match_name": s.get("match_name"),
                             "finding": "Sanctions match requires analyst investigation — not yet resolved"}

        return 30, {"status": "unknown_screening_result",
                    "finding": "Screening result could not be interpreted"}

    # =========================================================================
    # DIMENSION 2: IDENTITY VERIFICATION (20%)
    # =========================================================================

    def evaluate_identity_verification(self, customer_id: str) -> Tuple[float, Dict]:
        if self.id_verifications is None or len(self.id_verifications) == 0:
            return 0, {"status": "no_id_data", "finding": "No identity verification data available"}

        ids = self.id_verifications[self.id_verifications["customer_id"] == customer_id]

        if len(ids) == 0:
            return 0, {"status": "no_documents",
                       "finding": "No identity documents on file — minimum KYC standard not met"}

        statuses = ids["document_status"].value_counts().to_dict() if "document_status" in ids.columns else {}
        doc_types = ids["document_type"].unique().tolist() if "document_type" in ids.columns else []

        verified  = statuses.get("VERIFIED", 0)
        expired   = statuses.get("EXPIRED", 0)
        pending   = statuses.get("PENDING", 0)
        rejected  = statuses.get("REJECTED", 0)
        total     = len(ids)

        if verified > 0:
            score = 80 if expired > 0 else 100
            return score, {
                "status": "verified",
                "verified_count": verified,
                "expired_count": expired,
                "document_types": doc_types,
                "finding": f"{verified} verified document(s) on file"
                           + (f" — {expired} expired document(s) also present" if expired > 0 else "")
            }
        elif pending > 0:
            return 40, {"status": "pending",
                        "pending_count": pending,
                        "finding": f"Verification in progress — {pending} document(s) awaiting confirmation"}
        elif expired > 0 and rejected == 0:
            return 20, {"status": "all_expired",
                        "expired_count": expired,
                        "finding": f"All {expired} document(s) are expired — re-verification required"}
        else:
            return 0, {"status": "all_rejected",
                       "rejected_count": rejected,
                       "finding": f"All {rejected} document(s) rejected as invalid — identity cannot be established"}

    # =========================================================================
    # DIMENSION 3: ACCOUNT ACTIVITY (15%)
    # =========================================================================

    def evaluate_account_activity(self, customer_id: str) -> Tuple[float, Dict]:
        if self.transactions is None or len(self.transactions) == 0:
            return 50, {"status": "no_transaction_data",
                        "finding": "No transaction data available — activity cannot be assessed"}

        txn = self.transactions[self.transactions["customer_id"] == customer_id]

        if len(txn) == 0:
            return 30, {"status": "no_activity",
                        "finding": "No transaction activity on record"}

        t = txn.iloc[0]
        txn_count  = t.get("txn_count", 0) or 0
        total_vol  = t.get("total_volume", 0) or 0

        try:
            last_txn = pd.to_datetime(t.get("last_txn_date"))
            days_inactive = (datetime.now() - last_txn).days
        except Exception:
            days_inactive = None

        if days_inactive is not None and days_inactive > 365:
            score = 40
            finding = f"Account inactive for {days_inactive} days — dormancy risk"
        elif txn_count > 100:
            score = 90
            finding = f"Active account — {txn_count} transactions, volume {total_vol:,.0f}"
        elif txn_count > 20:
            score = 75
            finding = f"Normal activity — {txn_count} transactions"
        elif txn_count > 0:
            score = 60
            finding = f"Low activity — {txn_count} transactions on record"
        else:
            score = 30
            finding = "No transaction activity recorded"

        return score, {"status": "activity_assessed", "txn_count": int(txn_count),
                       "total_volume": float(total_vol), "days_inactive": days_inactive,
                       "finding": finding}

    # =========================================================================
    # DIMENSION 4: PROOF OF ADDRESS (15%)
    # =========================================================================

    def evaluate_proof_of_address(self, customer_id: str) -> Tuple[float, Dict]:
        if self.customers is None or len(self.customers) == 0:
            return 50, {"status": "no_customer_data", "finding": "No customer data available"}

        customer = self.customers[self.customers["customer_id"] == customer_id]
        if len(customer) == 0:
            return 0, {"status": "customer_not_found", "finding": "Customer record not found"}

        c = customer.iloc[0]
        jurisdiction = c.get("jurisdiction") or c.get("country_of_origin")

        if jurisdiction and str(jurisdiction).strip().lower() not in ("", "nan", "none"):
            return 80, {"status": "address_on_file",
                        "jurisdiction": jurisdiction,
                        "finding": f"Jurisdiction on record: {jurisdiction}"}

        return 40, {"status": "address_incomplete",
                    "finding": "Jurisdiction/address information is missing or incomplete"}

    # =========================================================================
    # DIMENSION 5: BENEFICIAL OWNERSHIP (15%)
    # =========================================================================

    def evaluate_beneficial_ownership(self, customer_id: str) -> Tuple[float, Dict]:
        if self.beneficial_owners is None or len(self.beneficial_owners) == 0:
            return 50, {"status": "no_ubo_data",
                        "finding": "No beneficial ownership data available"}

        ubos = self.beneficial_owners[self.beneficial_owners["customer_id"] == customer_id]

        if len(ubos) == 0:
            return 40, {"status": "no_ubo_record",
                        "finding": "No beneficial ownership records for this customer"}

        ubo_names = ubos["ubo_name"].dropna().tolist() if "ubo_name" in ubos.columns else []
        pcts = ubos["ownership_percentage"].dropna().tolist() if "ownership_percentage" in ubos.columns else []

        if not ubo_names:
            return 30, {"status": "insufficient_ubo_data",
                        "finding": "UBO records exist but names are missing — cannot confirm beneficial owners"}

        total_pct = sum(float(p) for p in pcts if p) if pcts else 0

        if total_pct >= 75:
            score = 100
        elif total_pct >= 50:
            score = 80
        elif total_pct > 0:
            score = 60
        else:
            score = 40

        return score, {
            "status": "ubo_identified",
            "ubo_count": len(ubo_names),
            "total_ownership_pct": round(total_pct, 1),
            "finding": f"{len(ubo_names)} UBO(s) identified — {total_pct:.1f}% ownership documented"
        }

    # =========================================================================
    # DIMENSION 6: DATA QUALITY (10%)
    # =========================================================================

    def evaluate_data_quality(self, customer_id: str) -> Tuple[float, Dict]:
        if self.customers is None or len(self.customers) == 0:
            return 50, {"status": "no_data", "finding": "No customer data available"}

        customer = self.customers[self.customers["customer_id"] == customer_id]
        if len(customer) == 0:
            return 0, {"status": "not_found", "finding": "Customer record not found"}

        c = customer.iloc[0]
        key_fields = ["customer_id", "entity_type", "jurisdiction", "risk_rating",
                      "account_open_date", "last_kyc_review_date", "country_of_origin"]
        null_count = sum(1 for f in key_fields if f in c.index and pd.isna(c[f]))
        total_fields = len([f for f in key_fields if f in c.index])

        try:
            review_date = pd.to_datetime(c.get("last_kyc_review_date"))
            days_since_review = (datetime.now() - review_date).days
        except Exception:
            days_since_review = 9999

        if null_count == 0:
            quality_rating = "Excellent"
            score = 100 if days_since_review <= 365 else 80 if days_since_review <= 730 else 60
        elif null_count <= 2:
            quality_rating = "Good"
            score = 70
        elif null_count <= 4:
            quality_rating = "Fair"
            score = 40
        else:
            quality_rating = "Poor"
            score = 20

        return score, {
            "status": "data_quality",
            "quality_rating": quality_rating,
            "null_fields": int(null_count),
            "total_fields": int(total_fields),
            "days_since_review": int(days_since_review) if days_since_review != 9999 else None,
            "finding": f"Data quality {quality_rating.lower()} — "
                       f"{null_count}/{total_fields} key fields missing"
                       + (f", last reviewed {days_since_review} days ago"
                          if days_since_review != 9999 else "")
        }

    # =========================================================================
    # DISPOSITION ENGINE
    # =========================================================================

    def determine_disposition(self, dimension_results: dict) -> dict:
        """
        Apply the versioned ruleset above the weighted score.

        Returns:
            disposition     : REJECT | REVIEW | PASS_WITH_NOTES | PASS
            triggered_rules : list of rule dicts that fired
            rationale       : plain-English explanation of the disposition
        """
        triggered_rejects = []
        triggered_reviews = []

        # Helper: check if a dimension detail field matches a rule condition
        def matches(rule: dict) -> bool:
            dim = rule["dimension"]
            field = rule["condition_field"]
            value = rule["condition_value"]
            details = dimension_results.get(f"{dim}_details", {})
            return str(details.get(field, "")).strip().lower() == str(value).strip().lower()

        # Check hard reject rules
        for rule in self.ruleset.get("hard_reject_rules", []):
            if matches(rule):
                triggered_rejects.append({
                    "rule_id": rule["rule_id"],
                    "name": rule["name"],
                    "description": rule["description"],
                    "policy_reference": rule.get("policy_reference", ""),
                    "dimension": rule["dimension"],
                })

        # Check review rules (only if no reject already triggered)
        for rule in self.ruleset.get("review_rules", []):
            if matches(rule):
                triggered_reviews.append({
                    "rule_id": rule["rule_id"],
                    "name": rule["name"],
                    "description": rule["description"],
                    "policy_reference": rule.get("policy_reference", ""),
                    "dimension": rule["dimension"],
                })

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
            triggered_reviews.append({
                "rule_id": "RV-SCORE",
                "name": "Score Below Minimum Threshold",
                "description": f"Weighted score {score} is below the {notes_min}-point floor.",
                "policy_reference": "Scoring Policy 1.1",
                "dimension": "composite",
            })

        return {
            "disposition": disposition,
            "triggered_reject_rules": triggered_rejects,
            "triggered_review_rules": triggered_reviews,
            "rationale": rationale,
            "ruleset_version": self.ruleset_version,
        }

    # =========================================================================
    # COMPOSITE EVALUATION
    # =========================================================================

    def evaluate_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Full evaluation: 6 dimensions → weighted score → disposition.
        """
        aml_score,  aml_details  = self.evaluate_aml_screening(customer_id)
        id_score,   id_details   = self.evaluate_identity_verification(customer_id)
        act_score,  act_details  = self.evaluate_account_activity(customer_id)
        poa_score,  poa_details  = self.evaluate_proof_of_address(customer_id)
        ubo_score,  ubo_details  = self.evaluate_beneficial_ownership(customer_id)
        dq_score,   dq_details   = self.evaluate_data_quality(customer_id)

        overall_score = round(
            aml_score  * self.DIMENSION_WEIGHTS["aml_screening"] +
            id_score   * self.DIMENSION_WEIGHTS["identity_verification"] +
            act_score  * self.DIMENSION_WEIGHTS["account_activity"] +
            poa_score  * self.DIMENSION_WEIGHTS["proof_of_address"] +
            ubo_score  * self.DIMENSION_WEIGHTS["beneficial_ownership"] +
            dq_score   * self.DIMENSION_WEIGHTS["data_quality"],
            1
        )

        result = {
            "customer_id":                    customer_id,
            "overall_score":                  overall_score,
            "aml_screening_score":            round(aml_score, 1),
            "aml_screening_details":          aml_details,
            "identity_verification_score":    round(id_score, 1),
            "identity_verification_details":  id_details,
            "account_activity_score":         round(act_score, 1),
            "account_activity_details":       act_details,
            "proof_of_address_score":         round(poa_score, 1),
            "proof_of_address_details":       poa_details,
            "beneficial_ownership_score":     round(ubo_score, 1),
            "beneficial_ownership_details":   ubo_details,
            "data_quality_score":             round(dq_score, 1),
            "data_quality_details":           dq_details,
            "evaluation_date":                datetime.now().isoformat(),
        }

        # Apply disposition layer
        disposition_result = self.determine_disposition(result)
        result.update(disposition_result)

        # Keep overall_status for backward compatibility with app.py display
        result["overall_status"] = disposition_result["disposition"]

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
            "customer_id", "overall_score", "disposition",
            "aml_screening_score", "identity_verification_score",
            "account_activity_score", "proof_of_address_score",
            "beneficial_ownership_score", "data_quality_score",
            "rationale", "ruleset_version",
        ]
        df = df[[c for c in score_cols if c in df.columns]]

        # Sort: disposition severity first, then score ascending within each bucket
        order = {"REJECT": 0, "REVIEW": 1, "PASS_WITH_NOTES": 2, "PASS": 3}
        df["_sort"] = df["disposition"].map(order).fillna(4)
        df = df.sort_values(["_sort", "overall_score"]).drop(columns=["_sort"])

        return df
