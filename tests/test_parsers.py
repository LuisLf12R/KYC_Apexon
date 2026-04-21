"""
tests/test_parsers.py
Tests for sources/parsers/ — PRS-001 through PRS-015
All tests use inline sample content — no HTTP, no disk I/O.
"""

import pytest

from sources.parsers import (
    ParseError,
    ParseResult,
    SanctionsEntry,
    list_parseable_sources,
    parse_source,
)
from sources.parsers.ofac_txt import parse_ofac_txt
from sources.parsers.ofsi_csv import parse_ofsi_csv
from sources.parsers.eu_xml import parse_eu_xml


# ── Sample content fixtures ────────────────────────────────────────────────────

OFAC_TXT_SAMPLE = """\n 36     ] AEROCARIBBEAN AIRLINES, Havana, Cuba; alt. name AERO-CARIBBEAN; [CUBA]
 37     ] ABRAMS, John Michael; DOB 01 Jan 1970; POB New York, USA; individual
         Additional address line for 37
 100    ] BLACK PEARL SHIPPING CO.; vessel; IMO 1234567
"""

OFSI_CSV_SAMPLE = """\nGroup ID,Name 1,Name 2,Name 3,Group Type,Other Field
1001,SMITH,JOHN,,Individual,foo
1002,EVIL CORP LTD,,,Entity,bar
1003,GHOST VESSEL,,, Ship,baz
"""

EU_XML_SAMPLE = """\n<?xml version="1.0" encoding="UTF-8"?>
<export>
  <sanctionEntity id="E001">
    <individual/>
    <nameAlias wholeName="JONES, Robert" strong="true"/>
    <nameAlias wholeName="JONES, Bob" strong="false"/>
  </sanctionEntity>
  <sanctionEntity id="E002">
    <nameAlias wholeName="DARK MONEY LLC" strong="true"/>
  </sanctionEntity>
  <sanctionEntity id="E003">
    <nameAlias firstName="Maria" lastName="GARCIA" strong="true"/>
    <individual/>
  </sanctionEntity>
</export>
"""


# ── PRS-001: OFAC TXT — correct entry count ───────────────────────────────────

def test_PRS_001_ofac_entry_count():
    result = parse_ofac_txt(OFAC_TXT_SAMPLE, "OFAC-SDN")
    assert result.ok
    assert result.entry_count == 3
    assert result.source_id == "OFAC-SDN"


# ── PRS-002: OFAC TXT — correct names extracted ───────────────────────────────

def test_PRS_002_ofac_names():
    result = parse_ofac_txt(OFAC_TXT_SAMPLE, "OFAC-SDN")
    names = [e.name for e in result.entries]
    assert any("AEROCARIBBEAN" in n for n in names)
    assert any("ABRAMS" in n for n in names)
    assert any("BLACK PEARL" in n for n in names)


# ── PRS-003: OFAC TXT — entity IDs match UID column ──────────────────────────

def test_PRS_003_ofac_entity_ids():
    result = parse_ofac_txt(OFAC_TXT_SAMPLE, "OFAC-SDN")
    ids = {e.entity_id for e in result.entries}
    assert "36" in ids
    assert "37" in ids
    assert "100" in ids


# ── PRS-004: OFAC TXT — type inference ────────────────────────────────────────

def test_PRS_004_ofac_type_inference():
    result = parse_ofac_txt(OFAC_TXT_SAMPLE, "OFAC-SDN")
    by_id = {e.entity_id: e for e in result.entries}
    assert by_id["37"].entry_type == "individual"
    assert by_id["100"].entry_type == "vessel"


# ── PRS-005: OFAC TXT — empty content raises ParseError ──────────────────────

def test_PRS_005_ofac_empty_raises():
    with pytest.raises(ParseError):
        parse_ofac_txt("", "OFAC-SDN")
    with pytest.raises(ParseError):
        parse_ofac_txt("   \n  ", "OFAC-CONS")


# ── PRS-006: OFSI CSV — correct entry count ───────────────────────────────────

def test_PRS_006_ofsi_entry_count():
    result = parse_ofsi_csv(OFSI_CSV_SAMPLE, "OFSI-CONS")
    assert result.ok
    assert result.entry_count == 3
    assert result.source_id == "OFSI-CONS"


# ── PRS-007: OFSI CSV — names and IDs ────────────────────────────────────────

def test_PRS_007_ofsi_names_and_ids():
    result = parse_ofsi_csv(OFSI_CSV_SAMPLE, "OFSI-CONS")
    by_id = {e.entity_id: e for e in result.entries}
    assert "1001" in by_id
    assert "SMITH" in by_id["1001"].name
    assert "JOHN" in by_id["1001"].name
    assert "1002" in by_id
    assert "EVIL CORP" in by_id["1002"].name


# ── PRS-008: OFSI CSV — type inference ───────────────────────────────────────

def test_PRS_008_ofsi_type_inference():
    result = parse_ofsi_csv(OFSI_CSV_SAMPLE, "OFSI-CONS")
    by_id = {e.entity_id: e for e in result.entries}
    assert by_id["1001"].entry_type == "individual"
    assert by_id["1002"].entry_type == "entity"
    assert by_id["1003"].entry_type == "vessel"


# ── PRS-009: OFSI CSV — missing Name 1 column raises ParseError ──────────────

def test_PRS_009_ofsi_missing_name_column():
    bad_csv = "Col A,Col B\nfoo,bar\n"
    with pytest.raises(ParseError, match="Name 1"):
        parse_ofsi_csv(bad_csv, "OFSI-CONS")


# ── PRS-010: EU XML — correct entry count ────────────────────────────────────

def test_PRS_010_eu_entry_count():
    result = parse_eu_xml(EU_XML_SAMPLE, "EU-CONS-SANCTIONS")
    assert result.ok
    assert result.entry_count == 3
    assert result.source_id == "EU-CONS-SANCTIONS"


# ── PRS-011: EU XML — names and IDs ──────────────────────────────────────────

def test_PRS_011_eu_names_and_ids():
    result = parse_eu_xml(EU_XML_SAMPLE, "EU-CONS-SANCTIONS")
    by_id = {e.entity_id: e for e in result.entries}
    assert "E001" in by_id
    assert "JONES" in by_id["E001"].name
    assert "E002" in by_id
    assert "DARK MONEY" in by_id["E002"].name


# ── PRS-012: EU XML — aliases captured ───────────────────────────────────────

def test_PRS_012_eu_aliases():
    result = parse_eu_xml(EU_XML_SAMPLE, "EU-CONS-SANCTIONS")
    by_id = {e.entity_id: e for e in result.entries}
    assert any("Bob" in a for a in by_id["E001"].aliases)


# ── PRS-013: EU XML — type inference ─────────────────────────────────────────

def test_PRS_013_eu_type_inference():
    result = parse_eu_xml(EU_XML_SAMPLE, "EU-CONS-SANCTIONS")
    by_id = {e.entity_id: e for e in result.entries}
    assert by_id["E001"].entry_type == "individual"
    assert by_id["E002"].entry_type == "entity"
    assert by_id["E003"].entry_type == "individual"


# ── PRS-014: dispatch — parse_source routes correctly ────────────────────────

def test_PRS_014_dispatch_routes():
    result = parse_source("OFAC-SDN", OFAC_TXT_SAMPLE)
    assert result.source_id == "OFAC-SDN"
    assert result.entry_count == 3

    result = parse_source("OFSI-CONS", OFSI_CSV_SAMPLE)
    assert result.source_id == "OFSI-CONS"

    result = parse_source("EU-CONS-SANCTIONS", EU_XML_SAMPLE)
    assert result.source_id == "EU-CONS-SANCTIONS"


# ── PRS-015: dispatch — unknown source_id raises ParseError ──────────────────

def test_PRS_015_dispatch_unknown_source():
    with pytest.raises(ParseError, match="No direct parser"):
        parse_source("UNKNOWN-SOURCE", "content")

    registered = list_parseable_sources()
    assert "OFAC-SDN" in registered
    assert "OFAC-CONS" in registered
    assert "OFSI-CONS" in registered
    assert "EU-CONS-SANCTIONS" in registered
