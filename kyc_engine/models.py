"""
kyc_engine/models.py
Pydantic v2 models for KYC engine inputs and outputs.

These models describe the *shape* of data flowing through the engine.
engine.py continues to return plain dicts; callers (dashboard, release
pipeline, institution overlay) use these models for validation and typing.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Disposition ────────────────────────────────────────────────────────────────

class DispositionLevel(str, Enum):
    PASS = "PASS"
    PASS_WITH_NOTES = "PASS_WITH_NOTES"
    REVIEW = "REVIEW"
    REJECT = "REJECT"

    @classmethod
    def severity_order(cls) -> Dict["DispositionLevel", int]:
        """Lower = more severe."""
        return {cls.REJECT: 0, cls.REVIEW: 1, cls.PASS_WITH_NOTES: 2, cls.PASS: 3}

    def is_more_severe_than(self, other: "DispositionLevel") -> bool:
        order = self.severity_order()
        return order[self] < order[other]


# ── Triggered rules ────────────────────────────────────────────────────────────

class TriggeredRule(BaseModel):
    rule_id: str
    name: str
    description: str
    policy_reference: str = ""
    dimension: str

    model_config = {"extra": "ignore"}


# ── Dimension detail blocks ────────────────────────────────────────────────────

class DimensionDetails(BaseModel):
    """Base shape for per-dimension detail dicts embedded in CustomerDecision."""
    status: str
    finding: str = ""

    model_config = {"extra": "allow"}


class AMLScreeningDetails(DimensionDetails):
    hit_status: str = ""


class DataQualityDetails(DimensionDetails):
    quality_rating: str = ""


# ── Customer decision (full evaluate_customer output) ─────────────────────────

class CustomerDecision(BaseModel):
    """
    Validated representation of the dict returned by
    KYCComplianceEngine.evaluate_customer().

    engine.py continues to return plain dicts; use
        CustomerDecision.model_validate(result)
    to validate and type-check the output.
    """

    customer_id: str
    jurisdiction: str
    overall_score: float = Field(ge=0.0, le=100.0)

    # Per-dimension scores
    aml_screening_score: float = Field(ge=0.0, le=100.0)
    identity_verification_score: float = Field(ge=0.0, le=100.0)
    account_activity_score: float = Field(ge=0.0, le=100.0)
    proof_of_address_score: float = Field(ge=0.0, le=100.0)
    beneficial_ownership_score: float = Field(ge=0.0, le=100.0)
    data_quality_score: float = Field(ge=0.0, le=100.0)
    source_of_wealth_score: float = Field(default=0.0, ge=0.0, le=100.0)
    crs_fatca_score: float = Field(default=0.0, ge=0.0, le=100.0)

    # Per-dimension detail dicts — stored as raw dicts to avoid
    # coupling models to dimension internals; callers can sub-validate.
    aml_screening_details: Dict[str, Any] = Field(default_factory=dict)
    identity_verification_details: Dict[str, Any] = Field(default_factory=dict)
    account_activity_details: Dict[str, Any] = Field(default_factory=dict)
    proof_of_address_details: Dict[str, Any] = Field(default_factory=dict)
    beneficial_ownership_details: Dict[str, Any] = Field(default_factory=dict)
    data_quality_details: Dict[str, Any] = Field(default_factory=dict)
    source_of_wealth_details: Dict[str, Any] = Field(default_factory=dict)
    crs_fatca_details: Dict[str, Any] = Field(default_factory=dict)

    # Raw dimension results (full evaluate output per dimension)
    dimension_results: Dict[str, Any] = Field(default_factory=dict)

    # Disposition
    disposition: DispositionLevel
    overall_status: DispositionLevel
    triggered_reject_rules: List[TriggeredRule] = Field(default_factory=list)
    triggered_review_rules: List[TriggeredRule] = Field(default_factory=list)
    rationale: str
    ruleset_version: str

    # Timestamp — accept str (ISO format) or datetime
    evaluation_date: str = ""

    model_config = {"extra": "ignore"}

    @field_validator("disposition", "overall_status", mode="before")
    @classmethod
    def coerce_disposition(cls, v: Any) -> str:
        return str(v).strip()

    @property
    def is_rejected(self) -> bool:
        return self.disposition == DispositionLevel.REJECT

    @property
    def requires_review(self) -> bool:
        return self.disposition in (DispositionLevel.REJECT, DispositionLevel.REVIEW)


# ── Disposition-only sub-result (determine_disposition output) ─────────────────

class DispositionResult(BaseModel):
    """Validated shape of the dict returned by determine_disposition()."""
    disposition: DispositionLevel
    triggered_reject_rules: List[TriggeredRule] = Field(default_factory=list)
    triggered_review_rules: List[TriggeredRule] = Field(default_factory=list)
    rationale: str
    ruleset_version: str

    model_config = {"extra": "ignore"}

    @field_validator("disposition", mode="before")
    @classmethod
    def coerce_disposition(cls, v: Any) -> str:
        return str(v).strip()


# ── Convenience re-exports ─────────────────────────────────────────────────────

__all__ = [
    "DispositionLevel",
    "TriggeredRule",
    "DimensionDetails",
    "AMLScreeningDetails",
    "DataQualityDetails",
    "CustomerDecision",
    "DispositionResult",
]
