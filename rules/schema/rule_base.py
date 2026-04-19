from __future__ import annotations
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, HttpUrl, field_validator


class RuleProvenance(BaseModel):
    """
    Required on every rule. Captures the authoritative regulatory source
    so every rule can be traced, replayed, and diffed across ruleset versions.

    Fields:
        regulator       Short name of issuing body. E.g. "FATF", "FinCEN", "FCA",
                        "Wolfsberg", "FINMA", "MAS", "HKMA", "AUSTRAC".
        jurisdiction    Scope of the rule. Use ISO 3166-1 alpha-3 for countries
                        (USA, GBR, CHE, SGP, HKG, AUS), "EU" for directives,
                        "supranational" for FATF/Wolfsberg.
        source_url      Direct URL to the authoritative document (PDF or web page).
                        For hand-authored rules, link to the most granular public
                        reference available.
        snapshot_hash   SHA-256 of the fetched source document at time of authoring.
                        Null for hand-authored rules where no fetch occurred.
        published_at    Date the regulator published this guidance. Null if unknown.
        effective_from  Date from which this rule is operationally in effect.
                        Use the document's stated effective date; if absent, use
                        published_at; if absent, use the ruleset effective_date.
        effective_until None means the rule is open-ended (no sunset date).
                        Set when a rule has a known expiry or has been superseded.
        regulatory_refs Human-readable list of the specific articles, recommendations,
                        or sections this rule implements. Minimum one entry required.
                        Examples:
                          ["FATF Rec 10", "FATF Rec 22"]
                          ["MLR 2017 reg 28(10)", "JMLSG Part I 5.3.15"]
                          ["FinCEN CDD Rule 31 CFR 1010.230"]
    """

    regulator: str
    jurisdiction: str
    source_url: HttpUrl
    snapshot_hash: Optional[str] = None
    published_at: Optional[date] = None
    effective_from: date
    effective_until: Optional[date] = None
    regulatory_refs: List[str]

    @field_validator("regulatory_refs")
    @classmethod
    def refs_not_empty(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("regulatory_refs must contain at least one entry")
        return v

    @field_validator("snapshot_hash")
    @classmethod
    def valid_sha256(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) != 64:
            raise ValueError("snapshot_hash must be a 64-character SHA-256 hex string")
        return v


class HardRejectRule(BaseModel):
    """
    A rule that, when triggered, unconditionally sets disposition to REJECT.
    No score threshold can override a hard reject.
    """
    rule_id: str
    name: str
    description: str
    dimension: str
    condition_field: str
    condition_value: str
    policy_reference: str
    provenance: RuleProvenance


class ReviewRule(BaseModel):
    """
    A rule that, when triggered, sets disposition to REVIEW.
    Engine evaluates all hard rejects first; if none hit, reviews are evaluated.
    """
    rule_id: str
    name: str
    description: str
    dimension: str
    condition_field: str
    condition_value: str
    policy_reference: str
    provenance: RuleProvenance
