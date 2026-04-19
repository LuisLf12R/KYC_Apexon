from abc import ABC, abstractmethod
from typing import Dict, List, Any
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


class BaseDimension(ABC):
    """Abstract base for all KYC dimensions."""

    STATUS_COMPLIANT = "Compliant"
    STATUS_NEEDS_REVIEW = "Needs Review"
    STATUS_ERROR = "Error"

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def evaluate(self, customer_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate this dimension for a single customer."""
        pass

    def batch_evaluate(
        self,
        customer_ids: List[str],
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Evaluate multiple customers safely with shared batch metadata."""
        results = []

        batch_ran_at = datetime.now().isoformat()
        batch_id = f"{self.__class__.__name__}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        for cid in customer_ids:
            try:
                result = self.evaluate(cid, data)

                # Attach shared batch metadata to every successful business result
                result["batch_ran_at"] = batch_ran_at
                result["batch_id"] = batch_id

            except Exception as e:
                logger.exception(
                    "Unexpected error in %s for customer_id=%s",
                    self.__class__.__name__,
                    cid
                )
                result = self._error_result(
                    customer_id=cid,
                    message=f"Unexpected error during evaluation: {str(e)}",
                    batch_ran_at=batch_ran_at,
                    batch_id=batch_id
                )

            results.append(result)

        return results

    def _build_result(
        self,
        customer_id: str,
        passed: bool,
        status: str,
        checks: Dict[str, Any],
        findings: List[str],
        batch_ran_at: str = None,
        batch_id: str = None
    ) -> Dict[str, Any]:
        """Build a standardized dimension result."""
        return {
            "customer_id": customer_id,
            "dimension": self.__class__.__name__,
            "passed": passed,
            "status": status,
            "checks": checks,
            "findings": findings,
            "evaluated_at": datetime.now().isoformat(),
            "batch_ran_at": batch_ran_at,
            "batch_id": batch_id
        }

    def _pass_result(
        self,
        customer_id: str,
        checks: Dict[str, Any],
        findings: List[str],
        batch_ran_at: str = None,
        batch_id: str = None
    ) -> Dict[str, Any]:
        """Helper: build result dict for passing check."""
        return self._build_result(
            customer_id=customer_id,
            passed=True,
            status=self.STATUS_COMPLIANT,
            checks=checks,
            findings=findings,
            batch_ran_at=batch_ran_at,
            batch_id=batch_id
        )

    def _fail_result(
        self,
        customer_id: str,
        checks: Dict[str, Any],
        findings: List[str],
        batch_ran_at: str = None,
        batch_id: str = None
    ) -> Dict[str, Any]:
        """Helper: build result dict for failing check."""
        return self._build_result(
            customer_id=customer_id,
            passed=False,
            status=self.STATUS_NEEDS_REVIEW,
            checks=checks,
            findings=findings,
            batch_ran_at=batch_ran_at,
            batch_id=batch_id
        )

    def _error_result(
        self,
        customer_id: str,
        message: str,
        batch_ran_at: str = None,
        batch_id: str = None
    ) -> Dict[str, Any]:
        """Helper: build result dict for unexpected execution errors."""
        return self._build_result(
            customer_id=customer_id,
            passed=False,
            status=self.STATUS_ERROR,
            checks={},
            findings=[message],
            batch_ran_at=batch_ran_at,
            batch_id=batch_id
        )