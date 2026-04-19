from __future__ import annotations
from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

from .rule_base import HardRejectRule, ReviewRule
from .dimensions import DimensionParameters, JurisdictionOverlay


class DispositionLevel(BaseModel):
    description: str
    color: str
    requires_human_action: bool
    can_be_cleared_by: Optional[str]


class ScoreThresholds(BaseModel):
    pass_minimum: int = Field(..., ge=0, le=100)
    pass_with_notes_minimum: int = Field(..., ge=0, le=100)
    note: Optional[str] = None

    @model_validator(mode="after")
    def pass_above_notes(self) -> "ScoreThresholds":
        if self.pass_minimum <= self.pass_with_notes_minimum:
            raise ValueError(
                "pass_minimum must be strictly greater than pass_with_notes_minimum"
            )
        return self


class ChangelogEntry(BaseModel):
    version: str
    date: date
    change: str
    author: Optional[str] = None


class RulesetManifest(BaseModel):
    """
    Top-level schema for a versioned KYC ruleset file.

    Load and validate a ruleset file with:
        import json
        from rules.schema import RulesetManifest
        manifest = RulesetManifest.model_validate(json.loads(path.read_text()))

    The manifest is the single source of truth consumed by the engine.
    Phase 2 replaces all hardcoded engine constants with reads from
    manifest.dimension_parameters.<dimension>.<field>.
    """

    version: str = Field(..., description="Semver ruleset version string, e.g. 'kyc-rules-v1.1'")
    effective_date: date
    created_by: str
    description: str
    changelog: List[ChangelogEntry]
    disposition_levels: Dict[str, DispositionLevel]
    hard_reject_rules: List[HardRejectRule]
    review_rules: List[ReviewRule]
    score_thresholds: ScoreThresholds
    dimension_parameters: DimensionParameters
    jurisdictions: Dict[str, JurisdictionOverlay] = {}

    @model_validator(mode="after")
    def no_duplicate_rule_ids(self) -> "RulesetManifest":
        ids = [r.rule_id for r in self.hard_reject_rules] + \
              [r.rule_id for r in self.review_rules]
        dupes = [rid for rid in ids if ids.count(rid) > 1]
        if dupes:
            raise ValueError(f"Duplicate rule_ids found: {set(dupes)}")
        return self
