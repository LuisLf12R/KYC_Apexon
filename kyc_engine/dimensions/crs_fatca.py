"""
crs_fatca.py
------------
CRS / FATCA Reporting-Obligation Dimension.

Evaluates whether customers have the required tax-reporting documentation:
- CRS self-certification (tax residency declaration) for customers in
  CRS-participating jurisdictions
- W-8 or W-9 form for FATCA-applicable customers

Customer record fields read:
    crs_self_cert_on_file   : "Y" / "N" / absent (treated as "N")
    fatca_status            : "exempt" | "w9_on_file" | "w8_on_file" | absent
    w8_w9_on_file           : "Y" / "N" / absent (fallback for fatca_status)

Compliance statuses emitted (used as condition_value in review_rules):
    crs_and_fatca_ok        : all applicable obligations met — passes
    crs_cert_missing        : CRS self-cert absent for CRS jurisdiction
    w8_w9_missing           : W-8/W-9 absent for FATCA-applicable customer
    not_applicable          : jurisdiction/entity not in scope — passes
"""

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import logging

from rules.schema.dimensions import CRSFATCAParameters

logger = logging.getLogger(__name__)

_FATCA_OK_STATUSES = {"exempt", "w9_on_file", "w8_on_file"}

_STATUS_SCORES: Dict[str, int] = {
    "crs_and_fatca_ok": 90,
    "not_applicable": 90,
    "crs_cert_missing": 50,
    "w8_w9_missing": 50,
}


class CRSFATCADimension:
    """CRS / FATCA reporting-obligation compliance dimension."""

    def __init__(self, params: CRSFATCAParameters, evaluation_date=None):
        self.params = params
        self.evaluation_date = evaluation_date or datetime.now()
        self._fatca_jurs = {j.upper() for j in params.fatca_applicable_jurisdictions}
        self._crs_jurs = {j.upper() for j in params.crs_participating_jurisdictions}
        self._w8w9_entity_types = {e.upper() for e in params.w8_w9_required_entity_types}

    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            customers = data.get("customers", pd.DataFrame())
            if customers.empty or "customer_id" not in customers.columns:
                return self._error_result(customer_id, "customers DataFrame missing")

            cust_row = customers[customers["customer_id"] == customer_id]
            if cust_row.empty:
                return self._error_result(customer_id, f"Customer {customer_id} not found")

            customer = cust_row.iloc[0]
            jurisdiction = str(customer.get("jurisdiction", "")).strip().upper()
            entity_type = str(customer.get("entity_type", "INDIVIDUAL")).strip().upper()

            findings: List[str] = []
            issues: List[str] = []

            in_crs = jurisdiction in self._crs_jurs
            in_fatca = jurisdiction in self._fatca_jurs
            needs_w8w9 = entity_type in self._w8w9_entity_types

            if not in_crs and not in_fatca:
                return self._result(
                    customer_id, "not_applicable", True,
                    ["[INFO] Jurisdiction not in CRS or FATCA scope — not applicable"],
                )

            # CRS self-certification check
            if in_crs:
                crs_cert = str(customer.get("crs_self_cert_on_file", "")).strip().upper()
                if crs_cert == "Y":
                    findings.append("[PASS] CRS self-certification on file")
                else:
                    findings.append("[FAIL] CRS self-certification not on file")
                    issues.append("crs_cert_missing")

            # FATCA / W-8 / W-9 check
            if in_fatca and needs_w8w9:
                fatca_status = str(customer.get("fatca_status", "")).strip().lower()
                w8w9_flag = str(customer.get("w8_w9_on_file", "")).strip().upper()

                if fatca_status in _FATCA_OK_STATUSES:
                    findings.append(f"[PASS] FATCA status: {fatca_status}")
                elif w8w9_flag == "Y":
                    findings.append("[PASS] W-8/W-9 on file (w8_w9_on_file=Y)")
                else:
                    findings.append("[FAIL] No W-8/W-9 or valid FATCA status on file")
                    issues.append("w8_w9_missing")

            if not issues:
                status = "crs_and_fatca_ok"
                passed = True
            else:
                # Most severe issue wins for the condition_value trigger
                status = issues[0]
                passed = False

            return self._result(customer_id, status, passed, findings)

        except Exception as exc:
            logger.error("Error evaluating CRS/FATCA for %s: %s", customer_id, exc)
            return self._error_result(customer_id, str(exc))

    def _result(
        self,
        customer_id: str,
        status: str,
        passed: bool,
        findings: List[str],
    ) -> Dict[str, Any]:
        return {
            "customer_id": customer_id,
            "dimension": "CRSFATCA",
            "passed": passed,
            "status": "Compliant" if passed else "Non-Compliant",
            "score": _STATUS_SCORES.get(status, 50),
            "crs_fatca_status": status,
            "findings": findings,
            "remediation_required": not passed,
        }

    def _error_result(self, customer_id: str, msg: str) -> Dict[str, Any]:
        return {
            "customer_id": customer_id,
            "dimension": "CRSFATCA",
            "passed": False,
            "status": "Error",
            "score": 0,
            "crs_fatca_status": "not_applicable",
            "findings": [f"Error: {msg}"],
            "remediation_required": True,
        }
