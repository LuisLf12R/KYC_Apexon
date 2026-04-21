"""
sources/parsers/ofsi_csv.py

Parser for OFSI Consolidated List of Financial Sanctions Targets (CSV format).

OFSI CSV format:
  Columns vary by release but always include group identifier and name fields.
  Known stable columns (case-insensitive match applied):
    - "Group ID"         → entity_id
    - "Name 1"           → primary name component (surname or full org name)
    - "Name 2"           → given name (individuals) or additional org name
    - "Name 3"-"Name 6"  → additional name parts (optional)
    - "Group Type"       → "Individual" | "Entity" | "Ship"

  When "Name 1" is absent, the row is skipped with a parse warning.

Used for: OFSI-CONS
"""

from __future__ import annotations

import csv
import io
from typing import List

from .base import ParseError, ParseResult, SanctionsEntry


def _normalise_headers(headers: List[str]) -> dict:
    """Return a lowercase-keyed map from canonical name to actual column index."""
    return {h.strip().lower(): i for i, h in enumerate(headers)}


def _join_name_parts(row: List[str], col_map: dict) -> str:
    """Concatenate Name 1 through Name 6 into a single name string."""
    parts = []
    for key in ["name 1", "name 2", "name 3", "name 4", "name 5", "name 6"]:
        if key in col_map:
            val = row[col_map[key]].strip() if col_map[key] < len(row) else ""
            if val:
                parts.append(val)
    return " ".join(parts)


def _infer_type(row: List[str], col_map: dict) -> str:
    if "group type" in col_map:
        raw = row[col_map["group type"]].strip().lower() if col_map["group type"] < len(row) else ""
        if raw == "individual":
            return "individual"
        if raw == "ship":
            return "vessel"
        if raw:
            return "entity"
    return "unknown"


def parse_ofsi_csv(content: str, source_id: str = "OFSI-CONS") -> ParseResult:
    """
    Parse OFSI CSV format sanctions list content.

    Parameters
    ----------
    content   : Full text content of the OFSI .csv file (UTF-8 string).
    source_id : Registry source ID (default "OFSI-CONS").

    Returns
    -------
    ParseResult
    """
    if not content or not content.strip():
        raise ParseError(f"Empty content received for {source_id}")

    content = content.strip()
    reader = csv.reader(io.StringIO(content))
    try:
        headers = next(reader)
    except StopIteration:
        raise ParseError(f"CSV has no header row: {source_id}")

    col_map = _normalise_headers(headers)

    if "name 1" not in col_map:
        raise ParseError(
            f"OFSI CSV missing required 'Name 1' column. "
            f"Found columns: {list(col_map.keys())}"
        )

    entries: List[SanctionsEntry] = []
    errors: List[str] = []

    for rowno, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue  # blank row

        name = _join_name_parts(row, col_map)
        if not name:
            errors.append(f"Row {rowno}: no name fields populated — skipped")
            continue

        group_id_col = col_map.get("group id", col_map.get("groupid"))
        entity_id = (
            row[group_id_col].strip()
            if group_id_col is not None and group_id_col < len(row)
            else f"row-{rowno}"
        )

        entries.append(
            SanctionsEntry(
                source_id=source_id,
                entity_id=entity_id,
                name=name,
                aliases=[],
                entry_type=_infer_type(row, col_map),
            )
        )

    return ParseResult(
        source_id=source_id,
        entry_count=len(entries),
        entries=entries,
        parse_errors=errors,
    )
