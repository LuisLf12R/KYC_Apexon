"""
rules/schema/institution.py

Pydantic schema for institution-level policy overlays.

An institution overlay sits above the jurisdiction overlay in the merge chain:
    baseline → jurisdiction_overlay → institution_overlay → engine params

Stored as JSON at rules/institutions/<INSTITUTION_ID>.json.
Never committed to the shared ruleset file — institution overlays are
loaded separately and applied at evaluation time.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class InstitutionOverlay(BaseModel):
    """
    Per-institution policy overlay applied on top of jurisdiction params.

    Only fields that differ from the jurisdiction (or baseline) need to be
    specified. Engine merges:
        get_jurisdiction_params(code) | institution.dimension_overrides

    Fields:
        institution_id      Unique identifier for this institution.
                            Used as the filename stem: BANK001.json
        institution_name    Human-readable name for audit trail display.
        jurisdiction_code   Must match the jurisdiction this institution
                            is booked under. Validated at load time.
        dimension_overrides Partial dimension parameter blocks, same
                            structure as JurisdictionOverlay.dimension_overrides.
                            Keys: identity | screening | beneficial_ownership |
                                  transactions | documents | data_quality
        policy_notes        Free-text explanation of why these overrides
                            exist (e.g. "Wolfsberg-aligned EDD policy").
                            Recorded in audit log.
        active              If False, overlay is loaded but not applied.
                            Engine falls back to jurisdiction params.
    """

    institution_id: str
    institution_name: str
    jurisdiction_code: str
    dimension_overrides: Dict[str, Any] = {}
    policy_notes: Optional[str] = None
    active: bool = True

    model_config = {"extra": "ignore"}

    @field_validator("institution_id")
    @classmethod
    def id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("institution_id must not be empty")
        return v.strip()

    @field_validator("institution_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("institution_name must not be empty")
        return v.strip()

    @field_validator("jurisdiction_code")
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("jurisdiction_code must not be empty")
        return v.strip()
