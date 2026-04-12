from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any

# EXCEPTIONS

class ContractValidationError(Exception):
    """Raised when a dataset does not satisfy its canonical contract."""
    pass



# ENUMS

class EntityType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    LEGAL_ENTITY = "LEGAL_ENTITY"


class RiskRating(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DocumentCategory(str, Enum):
    POA = "POA"
    ID = "ID"
    INCOME = "INCOME"
    CORPORATE = "CORPORATE"
    OTHER = "OTHER"


class DocumentType(str, Enum):
    # PoA-related
    UTILITY_BILL = "UTILITY_BILL"
    BANK_STATEMENT = "BANK_STATEMENT"
    LEASE_AGREEMENT = "LEASE_AGREEMENT"
    GOVERNMENT_CORRESPONDENCE = "GOVERNMENT_CORRESPONDENCE"
    TAX_NOTICE = "TAX_NOTICE"
    COUNCIL_TAX_BILL = "COUNCIL_TAX_BILL"
    INSURANCE_CERTIFICATE = "INSURANCE_CERTIFICATE"
    REGISTRATION_CERTIFICATE = "REGISTRATION_CERTIFICATE"
    GOVERNMENT_ID_WITH_ADDRESS = "GOVERNMENT_ID_WITH_ADDRESS"
    DIGITAL_GOVERNMENT_VERIFICATION = "DIGITAL_GOVERNMENT_VERIFICATION"
    HOST_ATTESTATION = "HOST_ATTESTATION"
    STUDENT_LETTER = "STUDENT_LETTER"
    REFEREE_STATEMENT = "REFEREE_STATEMENT"

    # ID-related
    PASSPORT = "PASSPORT"
    NATIONAL_ID = "NATIONAL_ID"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    RESIDENCE_PERMIT = "RESIDENCE_PERMIT"
    VOTER_ID = "VOTER_ID"
    OTHER_GOVERNMENT_ID = "OTHER_GOVERNMENT_ID"


class SourceType(str, Enum):
    DOCUMENT = "DOCUMENT"
    GOVERNMENT_API = "GOVERNMENT_API"
    DIGITAL_ID_PROVIDER = "DIGITAL_ID_PROVIDER"
    REGISTRY = "REGISTRY"
    EXCEPTION_DOCUMENT = "EXCEPTION_DOCUMENT"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    PENDING_REVIEW = "PENDING_REVIEW"
    REJECTED = "REJECTED"
    NOT_VERIFIED = "NOT_VERIFIED"
    INCOMPLETE = "INCOMPLETE"


class SourceReliability(str, Enum):
    GOVERNMENT_AUTHORITATIVE = "GOVERNMENT_AUTHORITATIVE"
    INDEPENDENT_RELIABLE = "INDEPENDENT_RELIABLE"
    CUSTOMER_SUBMITTED_ONLY = "CUSTOMER_SUBMITTED_ONLY"
    UNKNOWN = "UNKNOWN"


class ExceptionType(str, Enum):
    NONE = "NONE"
    HOSTED_ADDRESS = "HOSTED_ADDRESS"
    STUDENT = "STUDENT"
    REFUGEE_ASYLUM = "REFUGEE_ASYLUM"
    HOMELESS_REFEREE = "HOMELESS_REFEREE"
    OTHER_APPROVED_EXCEPTION = "OTHER_APPROVED_EXCEPTION"


class ScreeningType(str, Enum):
    SANCTIONS = "SANCTIONS"
    PEP = "PEP"
    ADVERSE_MEDIA = "ADVERSE_MEDIA"
    INTERNAL_WATCHLIST = "INTERNAL_WATCHLIST"


class MatchResult(str, Enum):
    NO_HIT = "NO_HIT"
    POTENTIAL_MATCH = "POTENTIAL_MATCH"
    CONFIRMED_MATCH = "CONFIRMED_MATCH"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class ReviewStatus(str, Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    CLEARED = "CLEARED"
    ESCALATED = "ESCALATED"
    BLOCKED = "BLOCKED"


class ActivityProfileStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    MINOR_DEVIATION = "MINOR_DEVIATION"
    MATERIAL_DEVIATION = "MATERIAL_DEVIATION"
    NOT_ASSESSED = "NOT_ASSESSED"


class ControlType(str, Enum):
    DIRECT_OWNERSHIP = "DIRECT_OWNERSHIP"
    INDIRECT_OWNERSHIP = "INDIRECT_OWNERSHIP"
    SIGNIFICANT_CONTROL = "SIGNIFICANT_CONTROL"
    TRUSTEE = "TRUSTEE"
    OTHER = "OTHER"


class RuleDomain(str, Enum):
    POA = "POA"
    IDENTITY = "IDENTITY"
    SCREENING = "SCREENING"
    UBO = "UBO"
    CDD_REFRESH = "CDD_REFRESH"
    TRANSACTION_MONITORING = "TRANSACTION_MONITORING"


class RuleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FUTURE_EFFECTIVE = "FUTURE_EFFECTIVE"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"

# CONTRACT MODELS

@dataclass(frozen=True)
class DatasetContract:
    """
    Canonical schema definition for one dataset.

    This is intentionally business-rule agnostic.
    It only defines the shape and allowed values of prepared data.
    """
    name: str
    required_fields: Set[str]
    optional_fields: Set[str] = field(default_factory=set)
    date_fields: Set[str] = field(default_factory=set)
    enum_fields: Dict[str, Set[str]] = field(default_factory=dict)
    primary_key: Optional[List[str]] = None
    record_type: str = "dataframe"  # "dataframe" or "list_of_dicts"

    @property
    def allowed_fields(self) -> Set[str]:
        return self.required_fields | self.optional_fields


def _enum_values(enum_cls: Any) -> Set[str]:
    return {member.value for member in enum_cls}


# CONTRACT DEFINITIONS

CUSTOMERS_CONTRACT = DatasetContract(
    name="customers",
    required_fields={
        "customer_id",
        "entity_type",
        "customer_name",
        "jurisdiction",
        "risk_rating",
        "account_open_date",
        "last_kyc_review_date",
    },
    optional_fields={
        "customer_status",
        "residency_status",
        "customer_segment",
        "declared_address_line1",
        "declared_address_line2",
        "declared_address_city",
        "declared_address_state_region",
        "declared_address_postal_code",
        "declared_address_country",
        "address_last_updated_at",
        "pep_flag",
        "sanctions_country_exposure_flag",
        "expected_activity_level",
        "customer_created_at",
        "customer_updated_at",
    },
    date_fields={
        "account_open_date",
        "last_kyc_review_date",
        "address_last_updated_at",
        "customer_created_at",
        "customer_updated_at",
    },
    enum_fields={
        "entity_type": _enum_values(EntityType),
        "risk_rating": _enum_values(RiskRating),
    },
    primary_key=["customer_id"],
)


ID_VERIFICATIONS_CONTRACT = DatasetContract(
    name="id_verifications",
    required_fields={
        "verification_id",
        "customer_id",
        "document_type",
        "document_country",
        "document_number_masked",
        "issue_date",
        "expiry_date",
        "verification_date",
        "verification_status",
    },
    optional_fields={
        "source_type",
        "source_name",
        "verification_method",
        "source_reliability",
        "name_match_result",
        "dob_match_result",
        "address_on_id_flag",
        "issuing_authority",
        "is_current_record",
        "rejection_reason",
        "manual_review_flag",
        "verified_by",
    },
    date_fields={
        "issue_date",
        "expiry_date",
        "verification_date",
    },
    enum_fields={
        "document_type": _enum_values(DocumentType),
        "verification_status": _enum_values(VerificationStatus),
        "source_type": _enum_values(SourceType),
        "source_reliability": _enum_values(SourceReliability),
    },
    primary_key=["verification_id"],
)


DOCUMENTS_CONTRACT = DatasetContract(
    name="documents",
    required_fields={
        "document_id",
        "customer_id",
        "document_category",
        "document_type",
        "source_type",
        "issue_date",
        "expiry_date",
        "upload_date",
        "verification_status",
    },
    optional_fields={
        # PoA structured fields
        "poa_address_line1",
        "poa_address_line2",
        "poa_address_city",
        "poa_address_state_region",
        "poa_address_postal_code",
        "poa_address_country",

        # Metadata
        "source_name",
        "source_reliability",
        "issuing_country",
        "approval_status",
        "verified_at",
        "verified_by",
        "exception_type",
        "redacted_flag",
        "is_current_record",
        "rejection_reason",
        "document_hash",
        "ocr_extraction_confidence",
        "digital_verification_reference",
    },
    date_fields={
        "issue_date",
        "expiry_date",
        "upload_date",
        "verified_at",
    },
    enum_fields={
        "document_category": _enum_values(DocumentCategory),
        "document_type": _enum_values(DocumentType),
        "source_type": _enum_values(SourceType),
        "verification_status": _enum_values(VerificationStatus),
        "source_reliability": _enum_values(SourceReliability),
        "exception_type": _enum_values(ExceptionType),
    },
    primary_key=["document_id"],
)


SCREENINGS_CONTRACT = DatasetContract(
    name="screenings",
    required_fields={
        "screening_id",
        "customer_id",
        "screening_type",
        "screening_date",
        "screening_status",
        "match_result",
    },
    optional_fields={
        "provider_name",
        "list_name",
        "match_score",
        "match_confidence_band",
        "review_status",
        "reviewed_at",
        "reviewed_by",
        "hit_count",
        "true_match_flag",
        "false_positive_flag",
        "escalation_flag",
        "rescreen_required_flag",
        "next_screen_due_date",
    },
    date_fields={
        "screening_date",
        "reviewed_at",
        "next_screen_due_date",
    },
    enum_fields={
        "screening_type": _enum_values(ScreeningType),
        "match_result": _enum_values(MatchResult),
        "review_status": _enum_values(ReviewStatus),
    },
    primary_key=["screening_id"],
)


TRANSACTIONS_CONTRACT = DatasetContract(
    name="transactions",
    required_fields={
        "customer_id",
        "last_txn_date",
    },
    optional_fields={
        "txn_count_30d",
        "txn_count_90d",
        "txn_volume_30d",
        "txn_volume_90d",
        "cash_activity_flag",
        "cross_border_flag",
        "high_risk_country_flag",
        "unexpected_activity_flag",
        "dormant_to_active_flag",
        "activity_profile_status",
        "activity_last_reviewed_at",
    },
    date_fields={
        "last_txn_date",
        "activity_last_reviewed_at",
    },
    enum_fields={
        "activity_profile_status": _enum_values(ActivityProfileStatus),
    },
    primary_key=["customer_id"],
)


UBO_CONTRACT = DatasetContract(
    name="ubo",
    required_fields={
        "customer_id",
        "ubo_id",
        "ubo_name",
        "ownership_percent",
        "control_type",
        "ubo_jurisdiction",
        "ubo_verification_status",
    },
    optional_fields={
        "ubo_dob",
        "ubo_nationality",
        "ubo_pep_flag",
        "ubo_sanctions_flag",
        "ubo_address_country",
        "ownership_chain_depth",
        "is_direct_owner",
        "is_control_person",
        "verification_date",
        "source_reliability",
        "supporting_documents_present",
        "rejection_reason",
    },
    date_fields={
        "ubo_dob",
        "verification_date",
    },
    enum_fields={
        "control_type": _enum_values(ControlType),
        "ubo_verification_status": _enum_values(VerificationStatus),
        "source_reliability": _enum_values(SourceReliability),
    },
    primary_key=["ubo_id"],
    record_type="list_of_dicts",
)


REGULATORY_RULES_CONTRACT = DatasetContract(
    name="regulatory_rules",
    required_fields={
        "rule_id",
        "jurisdiction",
        "rule_domain",
        "effective_date",
        "rule_status",
        "rule_summary",
    },
    optional_fields={
        "rule_severity",
        "impacted_dimension",
        "impacted_customer_type",
        "requires_backbook_remediation",
        "grace_period_days",
        "source_url",
        "source_reference",
        "supersedes_rule_id",
        "internal_policy_version",
        "implementation_status",
    },
    date_fields={
        "effective_date",
    },
    enum_fields={
        "rule_domain": _enum_values(RuleDomain),
        "rule_status": _enum_values(RuleStatus),
    },
    primary_key=["rule_id"],
    record_type="list_of_dicts",
)


CONTRACTS: Dict[str, DatasetContract] = {
    "customers": CUSTOMERS_CONTRACT,
    "id_verifications": ID_VERIFICATIONS_CONTRACT,
    "documents": DOCUMENTS_CONTRACT,
    "screenings": SCREENINGS_CONTRACT,
    "transactions": TRANSACTIONS_CONTRACT,
    "ubo": UBO_CONTRACT,
    "regulatory_rules": REGULATORY_RULES_CONTRACT,
}


# CONTRACT ACCESS HELPERS

def get_contract(dataset_name: str) -> DatasetContract:
    if dataset_name not in CONTRACTS:
        raise KeyError(f"Unknown dataset contract: {dataset_name}")
    return CONTRACTS[dataset_name]