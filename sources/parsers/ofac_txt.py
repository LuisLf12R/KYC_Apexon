"""
sources/parsers/ofac_txt.py

Parser for OFAC SDN and Consolidated Sanctions lists (TXT format).

OFAC TXT format (fixed/delimited):
  Each primary entry line matches the pattern:
      <whitespace> <numeric_uid> ] <NAME>, <additional fields...>

  Continuation lines (addresses, aliases, notes) begin without the UID ] marker.
  We parse primary lines only — continuation lines are skipped for now.

  Example:
      36    ] AEROCARIBBEAN AIRLINES, Havana, Cuba; ...
      -0-   [end of primary entry block marker, varies by list]

Used for: OFAC-SDN, OFAC-CONS
"""

from __future__ import annotations

import re
from typing import List

from .base import ParseError, ParseResult, SanctionsEntry

# Primary entry pattern: optional whitespace, digits, "]", name and rest
_PRIMARY_LINE = re.compile(r"^\s*(\d+)\s*\]\s*(.+)$")

# Common OFAC type indicators in the name field
_TYPE_HINTS = {
    "individual": ["individual", "a.k.a.", "f.k.a.", "dob", "pob"],
    "vessel": ["vessel", "imo", "call sign"],
    "entity": [],  # default for non-individual, non-vessel
}


def _infer_type(name_line: str) -> str:
    lower = name_line.lower()
    for hint in _TYPE_HINTS["individual"]:
        if hint in lower:
            return "individual"
    for hint in _TYPE_HINTS["vessel"]:
        if hint in lower:
            return "vessel"
    return "entity"


def _extract_primary_name(raw: str) -> str:
    """Extract the primary name from the field after ']'. Name ends at first ';' or ','."""
    # Name is everything before the first semicolon or end of field indicators
    parts = raw.split(";")[0].strip()
    # Remove trailing type classifiers like " [SDGT]"
    parts = re.sub(r"\s*\[.*?\]\s*$", "", parts).strip()
    return parts


def parse_ofac_txt(content: str, source_id: str) -> ParseResult:
    """
    Parse OFAC TXT format sanctions list content.

    Parameters
    ----------
    content   : Full text content of the OFAC .txt file.
    source_id : Registry source ID ("OFAC-SDN" or "OFAC-CONS").

    Returns
    -------
    ParseResult
    """
    if not content or not content.strip():
        raise ParseError(f"Empty content received for {source_id}")

    entries: List[SanctionsEntry] = []
    errors: List[str] = []

    for lineno, line in enumerate(content.splitlines(), start=1):
        m = _PRIMARY_LINE.match(line)
        if not m:
            continue
        uid = m.group(1).strip()
        rest = m.group(2).strip()
        if not rest:
            errors.append(f"Line {lineno}: empty name field for UID {uid}")
            continue

        name = _extract_primary_name(rest)
        if not name:
            errors.append(f"Line {lineno}: could not extract name for UID {uid}")
            continue

        entries.append(
            SanctionsEntry(
                source_id=source_id,
                entity_id=uid,
                name=name,
                aliases=[],
                entry_type=_infer_type(rest),
            )
        )

    return ParseResult(
        source_id=source_id,
        entry_count=len(entries),
        entries=entries,
        parse_errors=errors,
    )
