from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field


class IdentityParameters(BaseModel):
    """Parameters for the identity_verification dimension."""
    min_verified_docs: int = Field(
        ...,
        description="Minimum number of verified (non-rejected, non-expired) identity "
                    "documents required for a non-reject disposition.",
        ge=1,
    )
    doc_expiry_warning_days: int = Field(
        ...,
        description="Days before expiry at which a document is flagged as expiring-soon "
                    "in the dashboard. Does not affect disposition.",
        ge=0,
    )
    accepted_doc_types: List[str] = Field(
        ...,
        description="List of document type strings the engine treats as valid identity "
                    "documents. Strings must match values used in customer records. "
                    "Example: ['passport', 'national_id', 'driving_licence']",
        min_length=1,
    )


class ScreeningParameters(BaseModel):
    """Parameters for the aml_screening dimension."""
    max_screening_age_days: int = Field(
        ...,
        description="Maximum age in days of a screening record before it is considered "
                    "stale and triggers RV-003. Default baseline: 180.",
        ge=1,
    )
    fuzzy_match_threshold: float = Field(
        ...,
        description="Minimum fuzzy-match score (0.0–1.0) above which a name hit is "
                    "surfaced for analyst review. Below this score, hits are discarded "
                    "as noise.",
        ge=0.0,
        le=1.0,
    )


class BeneficialOwnershipParameters(BaseModel):
    """Parameters for the beneficial_ownership dimension."""
    ownership_threshold_pct: float = Field(
        ...,
        description="Percentage ownership at or above which a natural person must be "
                    "identified as a UBO. FATF baseline is 25%; some jurisdictions "
                    "require 10%. Express as a float: 25.0 = 25%%.",
        ge=0.0,
        le=100.0,
    )
    max_chain_depth: int = Field(
        ...,
        description="Maximum ownership chain depth the engine will traverse when "
                    "resolving UBOs through intermediate legal entities. "
                    "Depths beyond this are flagged as unresolved.",
        ge=1,
    )


class TransactionParameters(BaseModel):
    """Parameters for the transaction_monitoring dimension."""
    edd_trigger_threshold_usd: float = Field(
        ...,
        description="Single-transaction USD equivalent amount at or above which EDD "
                    "is triggered. Currency conversion uses engine's FX snapshot.",
        ge=0.0,
    )
    velocity_window_days: int = Field(
        ...,
        description="Rolling window in days used to compute transaction velocity "
                    "for pattern-based triggers.",
        ge=1,
    )


class DocumentParameters(BaseModel):
    """Parameters for the document_review dimension."""
    max_doc_age_days: int = Field(
        ...,
        description="Maximum age in days of any supporting document (e.g. proof of "
                    "address, SoW evidence) before it is treated as stale.",
        ge=1,
    )
    accepted_proof_of_address_types: List[str] = Field(
        ...,
        description="Document type strings accepted as proof of address. "
                    "Example: ['utility_bill', 'bank_statement', 'government_letter']",
        min_length=1,
    )


class DataQualityParameters(BaseModel):
    """Parameters for the data_quality dimension."""
    critical_fields: List[str] = Field(
        ...,
        description="Field names that, if missing or null, contribute to a Poor "
                    "data quality rating and may trigger RV-006. "
                    "Example: ['full_name', 'date_of_birth', 'nationality']",
        min_length=1,
    )
    poor_quality_threshold: float = Field(
        ...,
        description="Fraction of critical_fields that may be missing before the "
                    "record is rated Poor. Express as 0.0–1.0. "
                    "E.g. 0.2 means >20%% missing → Poor.",
        ge=0.0,
        le=1.0,
    )


class DimensionParameters(BaseModel):
    """
    Top-level container for all per-dimension rule parameters.
    Every field in engine methods that is currently a hardcoded constant
    must be moved here in Phase 2. Phase 1 defines the schema.
    """
    identity: IdentityParameters
    screening: ScreeningParameters
    beneficial_ownership: BeneficialOwnershipParameters
    transactions: TransactionParameters
    documents: DocumentParameters
    data_quality: DataQualityParameters
