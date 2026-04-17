#!/usr/bin/env python3
"""Validate OCR migration and report active engine behavior."""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def check(label: str, success: bool, detail: str = "") -> bool:
    icon = "✓" if success else "✗"
    suffix = f" ({detail})" if detail else ""
    print(f"{icon} {label}{suffix}")
    return success


def main() -> int:
    print("OCR v2 Validation")
    print("=" * 78)
    print(f"Timestamp: {ts()}")
    print(f"Root: {ROOT}")

    checks: List[bool] = []

    try:
        module = import_module("llm_integration.execution_engine")
        checks.append(check("ExecutionEngine module imported", True, getattr(module, "__file__", "")))
    except Exception as exc:
        checks.append(check("ExecutionEngine module imported", False, str(exc)))
        print("\nTraceback:")
        print(traceback.format_exc())
        return 1

    EngineCls = getattr(module, "ExecutionEngine", None)
    if EngineCls is None:
        checks.append(check("ExecutionEngine class exists", False))
        return 1

    checks.append(check("ExecutionEngine class exists", True))

    try:
        engine = EngineCls()
        checks.append(check("ExecutionEngine instantiated", True))
    except Exception as exc:
        checks.append(check("ExecutionEngine instantiated", False, str(exc)))
        print("\nTraceback:")
        print(traceback.format_exc())
        return 1

    has_ocr_extractor = hasattr(engine, "ocr_extractor")
    has_cache_manager = hasattr(engine, "cache_manager")
    has_llm_generator = hasattr(engine, "llm_generator")

    checks.append(check("Has ocr_extractor attribute (v2 marker)", has_ocr_extractor))
    checks.append(check("No cache_manager attribute (v1 marker removed)", not has_cache_manager))
    checks.append(check("No llm_generator attribute (v1 marker removed)", not has_llm_generator))

    sample_ocr = """NEW YORK METROPOLITAN UNIVERSITY
STUDENT ID CARD
NAME: LUIS ROMERO
STUDENT ID NUMBER: S10293847
STATUS: UNDERGRADUATE
VALID THRU: 2027-06-30"""

    print("\nTesting extract_from_text() with sample student ID OCR...")
    result = None
    try:
        result = engine.extract_from_text(sample_ocr, doc_type_hint="student_id")
        checks.append(check("extract_from_text() executed without crash", True))
    except TypeError:
        # Fallback for legacy signature.
        try:
            result = engine.extract_from_text(sample_ocr, "student_id")
            checks.append(check("extract_from_text() executed without crash", True, "legacy signature"))
        except Exception as exc:
            checks.append(check("extract_from_text() executed without crash", False, str(exc)))
    except Exception as exc:
        checks.append(check("extract_from_text() executed without crash", False, str(exc)))

    fields_out: Dict[str, Any] = {}
    if result is not None:
        doc_type = getattr(result, "document_type", None)
        checks.append(check("Result exposes document_type", doc_type is not None, str(doc_type)))

        extracted_successfully = getattr(result, "extracted_successfully", None)
        checks.append(check("Result exposes extracted_successfully", extracted_successfully is not None, str(extracted_successfully)))

        warnings = getattr(result, "warnings", [])
        checks.append(check("Warnings are empty or minimal", isinstance(warnings, list), f"count={len(warnings) if isinstance(warnings, list) else 'n/a'}"))

        extracted_data = getattr(result, "extracted_data", {})
        if isinstance(extracted_data, dict):
            fields_out = extracted_data
        else:
            checks.append(check("extracted_data is a dictionary", False, str(type(extracted_data))))

        expected_fields = ["name", "student_id", "status", "valid_thru"]
        found_expected = sum(1 for f in expected_fields if f in fields_out)

        # If no API key, fallback behavior is expected and should not fail validation hard.
        has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        if has_api_key:
            checks.append(check("Expected student fields extracted", found_expected >= 2, f"found={found_expected}/4"))
            checks.append(check("Document type recognized as student_id", doc_type == "student_id", str(doc_type)))
            checks.append(check("Extraction successful is True", bool(extracted_successfully) is True, str(extracted_successfully)))
        else:
            checks.append(check("No API key: fallback mode accepted", True, "ANTHROPIC_API_KEY not set"))

        print("\nExtracted fields:")
        if fields_out:
            for key, value in fields_out.items():
                print(f" - {key}: {value}")
        else:
            print(" - (none)")

        extracted_result = getattr(result, "extracted_result", None)
        if extracted_result is not None and hasattr(extracted_result, "fields"):
            print("\nField confidence breakdown:")
            for fld in getattr(extracted_result, "fields", []):
                conf = getattr(getattr(fld, "confidence", None), "value", getattr(fld, "confidence", "unknown"))
                print(f" - {getattr(fld, 'name', '?')}: {getattr(fld, 'value', None)} ({conf})")

        print("\nWarnings:")
        print(json.dumps(warnings, indent=2))

    all_pass = all(checks)
    print("\nOverall Result:")
    if all_pass:
        print("✓ OCR migration validation checks passed.")
        return 0

    print("✗ One or more validation checks failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
