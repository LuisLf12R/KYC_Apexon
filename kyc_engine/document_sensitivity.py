"""
kyc_engine/document_sensitivity.py
Sensitivity-keyword detection for uploaded documents.

Scans extracted text for markers that indicate the document may be
non-original, confidential, or otherwise requires special handling
before field extraction proceeds.

Detected categories:
- CONFIDENTIAL: document marked confidential / restricted
- SAMPLE: document is a sample or specimen, not an original
- DRAFT: document is a draft, not a finalised version
- WATERMARK: known watermark text detected
- REDACTED: critical fields appear masked or redacted

Each detection returns a SensitivityFlag with category, matched keyword,
severity (block | review | info), and a human-readable message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import re


@dataclass
class SensitivityFlag:
    """A single sensitivity detection on a document."""
    category: str       # CONFIDENTIAL | SAMPLE | DRAFT | WATERMARK | REDACTED
    keyword: str        # the actual text that triggered this flag
    severity: str       # block | review | info
    message: str        # human-readable explanation


# ── Keyword registry ────────────────────────────────────────────────────────

_KEYWORD_RULES: List[Dict] = [
    # CONFIDENTIAL markers
    {"pattern": r"\bconfidential\b", "category": "CONFIDENTIAL", "severity": "review",
     "message": "Document marked CONFIDENTIAL — verify authenticity before processing."},
    {"pattern": r"\brestricted\b", "category": "CONFIDENTIAL", "severity": "review",
     "message": "Document marked RESTRICTED — may require special handling."},
    {"pattern": r"\bprivate\s+and\s+confidential\b", "category": "CONFIDENTIAL", "severity": "review",
     "message": "Document marked PRIVATE AND CONFIDENTIAL."},
    {"pattern": r"\bnot\s+for\s+distribution\b", "category": "CONFIDENTIAL", "severity": "review",
     "message": "Document marked NOT FOR DISTRIBUTION."},

    # SAMPLE / SPECIMEN markers
    {"pattern": r"\bsample\b", "category": "SAMPLE", "severity": "block",
     "message": "Document appears to be a SAMPLE — not an original. Upload rejected."},
    {"pattern": r"\bspecimen\b", "category": "SAMPLE", "severity": "block",
     "message": "Document marked SPECIMEN — not valid for compliance purposes."},
    {"pattern": r"\bfor\s+demo(nstration)?\s+only\b", "category": "SAMPLE", "severity": "block",
     "message": "Document is for demonstration only — not an original."},

    # DRAFT markers
    {"pattern": r"\bdraft\b", "category": "DRAFT", "severity": "review",
     "message": "Document appears to be a DRAFT — confirm final version before proceeding."},
    {"pattern": r"\bpreliminary\b", "category": "DRAFT", "severity": "info",
     "message": "Document marked PRELIMINARY — may not be final."},

    # WATERMARK text patterns
    {"pattern": r"\bcopy\b", "category": "WATERMARK", "severity": "info",
     "message": "Document contains 'COPY' marking — verify it is an acceptable copy."},

    # REDACTED / masked field patterns
    {"pattern": r"X{3,}", "category": "REDACTED", "severity": "review",
     "message": "Redacted/masked fields detected (XXX pattern) — verify required data is visible."},
    {"pattern": r"\*{3,}", "category": "REDACTED", "severity": "review",
     "message": "Redacted/masked fields detected (*** pattern) — verify required data is visible."},
    {"pattern": r"\[redacted\]", "category": "REDACTED", "severity": "review",
     "message": "Explicitly redacted fields detected — required data may be missing."},
    {"pattern": r"\[removed\]", "category": "REDACTED", "severity": "review",
     "message": "Removed fields detected — required data may be missing."},
]


def detect_sensitivity(
    text: str,
    *,
    extra_keywords: Optional[List[Dict]] = None,
) -> List[SensitivityFlag]:
    """
    Scan extracted document text for sensitivity markers.

    Args:
        text: extracted text from a document (OCR or pdfplumber).
        extra_keywords: optional additional rules in the same format
                        as _KEYWORD_RULES entries.

    Returns:
        List of SensitivityFlag objects, deduplicated by category.
        Empty list means no sensitivity issues detected.
    """
    if not text or not text.strip():
        return []

    rules = list(_KEYWORD_RULES)
    if extra_keywords:
        rules.extend(extra_keywords)

    flags: List[SensitivityFlag] = []
    seen_categories: Set[str] = set()

    for rule in rules:
        pattern = rule["pattern"]
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            cat = rule["category"]
            # Only one flag per category (use the first / most severe match)
            if cat not in seen_categories:
                seen_categories.add(cat)
                flags.append(SensitivityFlag(
                    category=cat,
                    keyword=match.group(0),
                    severity=rule["severity"],
                    message=rule["message"],
                ))

    # Sort: block first, then review, then info
    severity_order = {"block": 0, "review": 1, "info": 2}
    flags.sort(key=lambda f: severity_order.get(f.severity, 9))

    return flags


def should_block(flags: List[SensitivityFlag]) -> bool:
    """Return True if any flag has severity='block'."""
    return any(f.severity == "block" for f in flags)


def requires_review(flags: List[SensitivityFlag]) -> bool:
    """Return True if any flag has severity='block' or 'review'."""
    return any(f.severity in ("block", "review") for f in flags)


def sensitivity_summary(flags: List[SensitivityFlag]) -> Dict:
    """Return a dict summary suitable for audit logging."""
    return {
        "flag_count": len(flags),
        "categories": list({f.category for f in flags}),
        "blocked": should_block(flags),
        "requires_review": requires_review(flags),
        "flags": [
            {
                "category": f.category,
                "keyword": f.keyword,
                "severity": f.severity,
                "message": f.message,
            }
            for f in flags
        ],
    }
