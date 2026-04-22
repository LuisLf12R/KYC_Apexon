"""
source_of_wealth.py
-------------------
Source of Wealth (SoW) Dimension for PWM KYC compliance.

Evaluates whether a customer's declared source of wealth is:
1. Present (declared on the customer record)
2. A recognized category (per ruleset accepted_sow_categories)
3. Supported by evidence documents (document_category = "SOW")
4. Evidence is fresh (within max_evidence_age_days)

Compliance statuses:
- sow_verified: declaration + recognized category + sufficient fresh evidence
- sow_declared_no_evidence: declaration present but evidence missing/stale
- sow_category_unrecognized: declaration present but category not in accepted list
- sow_not_declared: no sow_declared field on customer record
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd
import logging

from rules.schema.dimensions import SoWParameters

logger = logging.getLogger(__name__)


class SourceOfWealthDimension:
    """Source of Wealth compliance dimension."""

    _STATUS_SCORES: Dict[str, int] = {
        "sow_verified": 90,
        "sow_declared_no_evidence": 60,
        "sow_category_unrecognized": 50,
        "sow_not_declared": 20,
    }

    def __init__(self, params: SoWParameters, evaluation_date=None):
        self.params = params
        self.evaluation_date = evaluation_date or datetime.now()
        self._accepted = {c.lower() for c in params.accepted_sow_categories}

    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            customers = data.get("customers", pd.DataFrame())
            documents = data.get("documents", pd.DataFrame())

            # Locate customer record
            if customers.empty or "customer_id" not in customers.columns:
                return self._error_result(customer_id, "customers DataFrame missing")

            cust_row = customers[customers["customer_id"] == customer_id]
            if cust_row.empty:
                return self._error_result(customer_id, f"Customer {customer_id} not found")

            customer = cust_row.iloc[0]
            sow_declared = customer.get("sow_declared")

            findings: List[str] = []

            # [1] Declaration present?
            if pd.isna(sow_declared) or str(sow_declared).strip() == "":
                sow_status = "sow_not_declared"
                findings.append("[FAIL] No source of wealth declaration on customer record")
                passed = False
            else:
                sow_declared = str(sow_declared).strip().lower()

                # [2] Recognized category?
                if sow_declared not in self._accepted:
                    sow_status = "sow_category_unrecognized"
                    findings.append(
                        f"[WARN] Declared SoW category '{sow_declared}' not in accepted list"
                    )
                    findings.append(
                        f"[INFO] Accepted: {', '.join(sorted(self._accepted))}"
                    )
                    passed = False
                else:
                    findings.append(f"[PASS] SoW category '{sow_declared}' recognized")

                    # [3] Evidence documents present and fresh?
                    evidence_count, stale_count, ev_findings = self._check_evidence(
                        customer_id, documents
                    )
                    findings.extend(ev_findings)

                    if evidence_count >= self.params.min_evidence_docs and stale_count == 0:
                        sow_status = "sow_verified"
                        passed = True
                        findings.append(
                            f"[PASS] {evidence_count} fresh SoW evidence document(s) on file"
                        )
                    else:
                        sow_status = "sow_declared_no_evidence"
                        passed = False
                        if evidence_count == 0:
                            findings.append(
                                f"[FAIL] No SoW evidence documents found "
                                f"(min required: {self.params.min_evidence_docs})"
                            )
                        else:
                            findings.append(
                                f"[WARN] {stale_count} of {evidence_count} SoW document(s) stale"
                            )

            score = self._STATUS_SCORES.get(sow_status, 20)

            return {
                "customer_id": customer_id,
                "dimension": "SourceOfWealth",
                "passed": passed,
                "status": "Compliant" if passed else "Non-Compliant",
                "score": score,
                "sow_status": sow_status,
                "findings": findings,
                "remediation_required": not passed,
                "next_review_date": (
                    self.evaluation_date + timedelta(days=self.params.max_evidence_age_days)
                ).date().isoformat(),
            }

        except Exception as exc:
            logger.error("Error evaluating SoW for %s: %s", customer_id, exc)
            return self._error_result(customer_id, str(exc))

    def _check_evidence(
        self, customer_id: str, documents: pd.DataFrame
    ):
        """
        Locate SOW-category documents for this customer.
        Returns (fresh_count, stale_count, findings).
        """
        findings: List[str] = []

        if documents.empty or "customer_id" not in documents.columns:
            return 0, 0, findings

        cust_docs = documents[documents["customer_id"] == customer_id]

        if "document_category" in cust_docs.columns:
            sow_docs = cust_docs[
                cust_docs["document_category"].str.upper() == "SOW"
            ]
        else:
            sow_docs = pd.DataFrame()

        if sow_docs.empty:
            return 0, 0, findings

        cutoff = self.evaluation_date - timedelta(days=self.params.max_evidence_age_days)
        fresh_count = 0
        stale_count = 0

        for _, doc in sow_docs.iterrows():
            issue_date = pd.to_datetime(doc.get("issue_date"), errors="coerce")
            if pd.isna(issue_date):
                stale_count += 1
                findings.append("[WARN] SoW evidence document missing issue_date")
                continue
            if issue_date < cutoff:
                stale_count += 1
                findings.append(
                    f"[WARN] SoW evidence stale: issued {issue_date.date()} "
                    f"(max age: {self.params.max_evidence_age_days}d)"
                )
            else:
                fresh_count += 1

        return fresh_count, stale_count, findings

    def _error_result(self, customer_id: str, msg: str) -> Dict[str, Any]:
        return {
            "customer_id": customer_id,
            "dimension": "SourceOfWealth",
            "passed": False,
            "status": "Error",
            "score": 0,
            "sow_status": "sow_not_declared",
            "findings": [f"Error: {msg}"],
            "remediation_required": True,
            "next_review_date": self.evaluation_date.date().isoformat(),
        }
