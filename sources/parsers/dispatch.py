"""
sources/parsers/dispatch.py

Routes a direct-format source to its correct parser.

Usage:
    result = parse_source("OFAC-SDN", content_str)
    result = parse_source("EU-CONS-SANCTIONS", xml_str)
"""

from __future__ import annotations

from .base import ParseError, ParseResult
from .ofac_txt import parse_ofac_txt
from .ofsi_csv import parse_ofsi_csv
from .eu_xml import parse_eu_xml

# Map from registry source_id to parser callable
_PARSER_REGISTRY = {
    "OFAC-SDN": lambda content: parse_ofac_txt(content, "OFAC-SDN"),
    "OFAC-CONS": lambda content: parse_ofac_txt(content, "OFAC-CONS"),
    "OFSI-CONS": lambda content: parse_ofsi_csv(content, "OFSI-CONS"),
    "EU-CONS-SANCTIONS": lambda content: parse_eu_xml(content, "EU-CONS-SANCTIONS"),
}


def parse_source(source_id: str, content: str) -> ParseResult:
    """
    Dispatch content to the correct parser for the given source_id.

    Parameters
    ----------
    source_id : Registry source ID matching a direct parse_mode entry.
    content   : Raw file content as a string.

    Returns
    -------
    ParseResult

    Raises
    ------
    ParseError if source_id is not registered or parser fails fatally.
    """
    if source_id not in _PARSER_REGISTRY:
        raise ParseError(
            f"No direct parser registered for source_id={source_id!r}. "
            f"Registered: {sorted(_PARSER_REGISTRY.keys())}"
        )
    return _PARSER_REGISTRY[source_id](content)


def list_parseable_sources() -> list:
    """Return the list of source IDs with registered direct parsers."""
    return sorted(_PARSER_REGISTRY.keys())
