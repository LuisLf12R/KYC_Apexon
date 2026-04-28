"""
schema.py
---------
Strict contract for dimension evaluate() outputs.
All six core dimensions must conform to DimensionResult.
"""

from typing import Any

REQUIRED_KEYS = {
    "customer_id",
    "dimension",
    "passed",
    "status",
    "score",
    "findings",
    "remediation_required",
    "next_review_date",
    "evaluation_details",
}


def validate_dimension_result(result: dict[str, Any]) -> None:
    """
    Raise KeyError if a required key is absent.
    Raise ValueError if score is outside [0, 100].
    """
    for key in REQUIRED_KEYS:
        if key not in result:
            raise KeyError(f"DimensionResult missing required key: '{key}'")
    score = result["score"]
    if not isinstance(score, int) or isinstance(score, bool):
        raise ValueError(f"DimensionResult score must be an int, got {type(score).__name__!r}")
    if not (0 <= score <= 100):
        raise ValueError(f"DimensionResult score {score!r} out of range [0, 100]")
