"""
canonical_schemas.py
--------------------
Authoritative schema registry for the KYC engine. Defines exactly which
columns the engine reads per dataset type, which are critical (hard-reject
if >50% of rows can't be mapped), and which are nice-to-have (warn only).

This is the target schema for the schema harmonizer. It is NOT the same as
src/data/contracts/contracts.py — that file is descriptive documentation.
This file is operational truth: if it says a column is critical, the engine
needs it to score correctly.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class CanonicalSchema:
    """Schema definition for one engine-consumed dataset."""
    target_type: str
    critical_fields: List[str]
    nice_fields: List[str]
    enum_hints: Dict[str, List[str]] = field(default_factory=dict)
    date_fields: List[str] = field(default_factory=list)

    @property
    def all_fields(self) -> List[str]:
        return self.critical_fields + self.nice_fields


CUSTOMERS = CanonicalSchema(
    target_type="customers",
    critical_fields=[
        "customer_id",
        "entity_type",
        "risk_rating",
        "last_kyc_review_date",
    ],
    nice_fields=[
        "jurisdiction",
        "country_of_origin",
        "account_open_date",
    ],
    enum_hints={
        "entity_type": ["INDIVIDUAL", "LEGAL_ENTITY"],
        "risk_rating": ["LOW", "MEDIUM", "HIGH"],
    },
    date_fields=["last_kyc_review_date", "account_open_date"],
)

SCREENINGS = CanonicalSchema(
    target_type="screenings",
    critical_fields=[
        "customer_id",
        "screening_date",
        "screening_result",
    ],
    nice_fields=[
        "hit_status",
        "match_name",
        "list_reference",
    ],
    enum_hints={
        "screening_result": ["NO_MATCH", "MATCH"],
        "hit_status": ["CONFIRMED", "FALSE_POSITIVE", "UNDER_REVIEW"],
    },
    date_fields=["screening_date"],
)

ID_VERIFICATIONS = CanonicalSchema(
    target_type="id_verifications",
    critical_fields=[
        "customer_id",
        "document_type",
        "document_status",
        "expiry_date",
    ],
    nice_fields=[
        "issue_date",
        "verification_date",
        "document_number",
    ],
    enum_hints={
        "document_type": [
            "PASSPORT", "NATIONAL_ID", "DRIVERS_LICENSE",
            "RESIDENCE_PERMIT", "STATE_ID", "OTHER",
        ],
        "document_status": ["VERIFIED", "EXPIRED", "PENDING", "REJECTED"],
    },
    date_fields=["expiry_date", "issue_date", "verification_date"],
)

DOCUMENTS = CanonicalSchema(
    target_type="documents",
    critical_fields=[
        "customer_id",
        "document_type",
        "document_category",
    ],
    nice_fields=[
        "issue_date",
        "expiry_date",
        "verification_status",
    ],
    enum_hints={
        "document_category": ["POA", "ADDRESS"],
        "document_type": [
            "UTILITY_BILL", "BANK_STATEMENT", "LEASE_AGREEMENT",
            "GOVERNMENT_CORRESPONDENCE", "TAX_NOTICE", "COUNCIL_TAX_BILL",
            "INSURANCE_CERTIFICATE", "OTHER",
        ],
        "verification_status": ["VERIFIED", "PENDING", "REJECTED"],
    },
    date_fields=["issue_date", "expiry_date"],
)

TRANSACTIONS = CanonicalSchema(
    target_type="transactions",
    critical_fields=[
        "customer_id",
    ],
    nice_fields=[
        "last_txn_date",
        "txn_count",
        "total_volume",
    ],
    enum_hints={},
    date_fields=["last_txn_date"],
)

UBO = CanonicalSchema(
    target_type="ubo",
    critical_fields=[
        "customer_id",
        "ubo_name",
    ],
    nice_fields=[
        "ownership_percentage",
        "nationality",
        "date_identified",
    ],
    enum_hints={},
    date_fields=["date_identified"],
)


CANONICAL_SCHEMAS: Dict[str, CanonicalSchema] = {
    "customers": CUSTOMERS,
    "screenings": SCREENINGS,
    "id_verifications": ID_VERIFICATIONS,
    "documents": DOCUMENTS,
    "transactions": TRANSACTIONS,
    "ubo": UBO,
}


def get_schema(target_type: str) -> CanonicalSchema:
    if target_type not in CANONICAL_SCHEMAS:
        raise KeyError(f"Unknown target_type: {target_type}")
    return CANONICAL_SCHEMAS[target_type]
