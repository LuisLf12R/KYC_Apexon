"""
sources/parsers/base.py

Shared types for all direct sanctions-list parsers.

Architectural constraint (§7): sanctions lists are parsed, not LLM-extracted.
Parsers consume raw file content (str or bytes) and return structured results.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SanctionsEntry:
    """
    A single sanctioned entity extracted from a sanctions list.

    source_id   : Registry source ID (e.g. "OFAC-SDN").
    entity_id   : Identifier from the list (OFAC UID, OFSI Group ID, EU entity ID).
    name        : Primary name of the entity.
    aliases     : Additional names / aliases.
    entry_type  : "individual" | "entity" | "vessel" | "unknown"
    """
    source_id: str
    entity_id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    entry_type: str = "unknown"


@dataclass
class ParseResult:
    """
    Result of parsing a direct-format sanctions list.

    source_id       : Registry source ID.
    entry_count     : Total number of entries parsed.
    entries         : Parsed SanctionsEntry list.
    parse_errors    : Non-fatal warnings accumulated during parsing.
    """
    source_id: str
    entry_count: int
    entries: List[SanctionsEntry] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.entry_count > 0


class ParseError(Exception):
    """Raised when a parser cannot process the input at all (fatal)."""
