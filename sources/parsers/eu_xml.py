"""
sources/parsers/eu_xml.py

Parser for EU Consolidated Sanctions List (XML format, schema v1.1).

EU XML structure (relevant elements):
  <sanctionEntity id="...">
    <nameAlias wholeName="..." firstName="..." middleName="..." lastName="..."
               strong="true|false" />
    ...
  </sanctionEntity>

  Multiple <nameAlias> elements per entity; the first strong="true" alias
  (or the first alias if none are marked strong) is treated as the primary name.
  Remaining aliases are stored in SanctionsEntry.aliases.

  Entity type is inferred from child elements:
    <individual> present → "individual"
    otherwise            → "entity"

Used for: EU-CONS-SANCTIONS
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List, Optional

from .base import ParseError, ParseResult, SanctionsEntry


def _get_whole_name(alias_el: ET.Element) -> str:
    """Extract wholeName or reconstruct from first/middle/last."""
    whole = alias_el.get("wholeName", "").strip()
    if whole:
        return whole
    parts = [
        alias_el.get("firstName", ""),
        alias_el.get("middleName", ""),
        alias_el.get("lastName", ""),
    ]
    return " ".join(p.strip() for p in parts if p.strip())


def _parse_entity(entity_el: ET.Element, source_id: str) -> Optional[SanctionsEntry]:
    """Parse a single <sanctionEntity> element."""
    entity_id = entity_el.get("id", "").strip()
    if not entity_id:
        return None

    # Collect all nameAlias elements
    aliases_els = entity_el.findall("nameAlias")
    if not aliases_els:
        # Try with namespace prefix if bare tag fails
        aliases_els = [
            child for child in entity_el
            if child.tag.endswith("nameAlias")
        ]

    names = []
    for a in aliases_els:
        n = _get_whole_name(a)
        if n:
            names.append((n, a.get("strong", "false").lower() == "true"))

    if not names:
        return None

    # Primary name: first strong alias, or first alias if none are strong
    strong_names = [n for n, is_strong in names if is_strong]
    primary = strong_names[0] if strong_names else names[0][0]
    alias_list = [n for n, _ in names if n != primary]

    # Infer type
    has_individual = any(
        child.tag == "individual" or child.tag.endswith("individual")
        for child in entity_el
    )
    entry_type = "individual" if has_individual else "entity"

    return SanctionsEntry(
        source_id=source_id,
        entity_id=entity_id,
        name=primary,
        aliases=alias_list,
        entry_type=entry_type,
    )


def parse_eu_xml(content: str, source_id: str = "EU-CONS-SANCTIONS") -> ParseResult:
    """
    Parse EU Consolidated Sanctions List XML content.

    Parameters
    ----------
    content   : Full XML content as a string.
    source_id : Registry source ID (default "EU-CONS-SANCTIONS").

    Returns
    -------
    ParseResult
    """
    if not content or not content.strip():
        raise ParseError(f"Empty content received for {source_id}")

    content = content.strip()
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ParseError(f"XML parse error for {source_id}: {exc}") from exc

    # Find all sanctionEntity elements (with or without namespace)
    entity_els = root.findall(".//sanctionEntity")
    if not entity_els:
        entity_els = [
            el for el in root.iter()
            if el.tag == "sanctionEntity" or el.tag.endswith("}sanctionEntity")
        ]

    entries: List[SanctionsEntry] = []
    errors: List[str] = []

    for el in entity_els:
        try:
            entry = _parse_entity(el, source_id)
            if entry:
                entries.append(entry)
            else:
                errors.append(f"Entity id={el.get('id', '?')}: no usable name — skipped")
        except Exception as exc:
            errors.append(f"Entity id={el.get('id', '?')}: {exc}")

    return ParseResult(
        source_id=source_id,
        entry_count=len(entries),
        entries=entries,
        parse_errors=errors,
    )
