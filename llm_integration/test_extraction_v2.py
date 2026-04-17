"""Quick smoke tests for OCR extraction v2."""

from __future__ import annotations

import json
import os

from llm_integration.ocr_extractor_v2 import OCRExtractor


def _print_result(title, result):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)
    print("document_type:", result.recognized_doc_type.value)
    print("overall_quality:", result.overall_quality.value)
    print("extracted_successfully:", result.extracted_successfully)
    print("analysis_notes:", result.analysis_notes)
    print("fields:")
    for field in result.fields:
        print(f"  - {field.name}: {field.value} ({field.confidence.value})")
    print("result_json:")
    print(json.dumps(result.to_dict(), indent=2))


def run_tests() -> None:
    """Run focused v2 behavior checks with representative OCR strings."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Skipping live extractor tests.")
        return

    extractor = OCRExtractor()

    student_id_ocr = """
    APEXON UNIVERSITY\nSTUDENT ID CARD\nName: Luis Romero\nStudent ID: S10293847\nStatus: UNDERGRADUATE\nValid Thru: 2027-06-30
    """
    bank_statement_ocr = """
    EXEMPLAR BANK STATEMENT\nAccount Holder: Jane Doe\nAccount Number: 123456789\nStatement Period: 2026-03-01 to 2026-03-31\nOpening Balance: 1200.50\nClosing Balance: 1780.22
    """
    blurry_ocr = "??? 1l1l O0O ### unreadable -- smudged text"
    partial_ocr = "UTILITY BILL\nAccount Name: Alex Smith\nAmount Due: 89.40\nDue Date:"

    _print_result(
        "Test 1: Student ID extraction",
        extractor.extract_from_ocr_text(student_id_ocr, hint_doc_type="student_id"),
    )
    _print_result(
        "Test 2: Bank statement extraction",
        extractor.extract_from_ocr_text(bank_statement_ocr, hint_doc_type="bank_statement"),
    )
    _print_result(
        "Test 3: Blurry/unreadable fallback behavior",
        extractor.extract_from_ocr_text(blurry_ocr),
    )
    _print_result(
        "Test 4: Partial/missing fields behavior",
        extractor.extract_from_ocr_text(partial_ocr, hint_doc_type="utility_bill"),
    )


if __name__ == "__main__":
    run_tests()
