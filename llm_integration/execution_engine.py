"""Execution engine v2: OCR + single-step structured extraction."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from llm_integration.ocr_handler import ocr_from_file
from llm_integration.ocr_extractor_v2 import (
    DocumentType,
    ExtractionConfidence,
    ExtractionResult,
    OCRExtractor,
)


@dataclass
class ExecutionResult:
    """Result returned by extraction engine v2."""

    extracted_data: Dict
    extracted_result: ExtractionResult
    source: str
    ocr_confidence: float
    extraction_confidence: str
    execution_time_seconds: float
    warnings: List[str]
    document_type: str
    extracted_successfully: bool


class ExecutionEngine:
    """Simplified v2 orchestrator with no cache and no dynamic code execution."""

    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize OCR extractor client."""
        self.ocr_extractor = OCRExtractor(api_key=anthropic_api_key)

    def extract_from_image(
        self,
        image_path: str,
        doc_type_hint: Optional[str] = None,
    ) -> ExecutionResult:
        """Run v2 extraction pipeline from image path."""
        start_time = time.time()
        warnings: List[str] = []

        try:
            ocr_result = ocr_from_file(image_path)
            ocr_text = ocr_result.full_text
            ocr_confidence = float(ocr_result.confidence)
            warnings.extend(ocr_result.warnings)
        except Exception as exc:
            fallback = self._build_engine_fallback_result(
                error_message=f"OCR extraction failed: {exc}",
                ocr_confidence=0.0,
            )
            fallback.execution_time_seconds = time.time() - start_time
            return fallback

        extracted_result = self.ocr_extractor.extract_from_ocr_text(
            ocr_text=ocr_text,
            hint_doc_type=doc_type_hint,
        )

        if not extracted_result.extracted_successfully:
            warnings.append(f"Extraction fallback used: {extracted_result.analysis_notes}")

        result = self._to_execution_result(
            extracted_result=extracted_result,
            ocr_confidence=ocr_confidence,
            warnings=warnings,
        )
        result.execution_time_seconds = time.time() - start_time
        return result

    def extract_from_text(
        self,
        ocr_text: str,
        doc_type_hint: Optional[str] = None,
    ) -> ExecutionResult:
        """Run v2 extraction pipeline directly from OCR text."""
        start_time = time.time()

        extracted_result = self.ocr_extractor.extract_from_ocr_text(
            ocr_text=ocr_text,
            hint_doc_type=doc_type_hint,
        )

        warnings: List[str] = []
        if not extracted_result.extracted_successfully:
            warnings.append(f"Extraction fallback used: {extracted_result.analysis_notes}")

        result = self._to_execution_result(
            extracted_result=extracted_result,
            ocr_confidence=1.0,
            warnings=warnings,
        )
        result.execution_time_seconds = time.time() - start_time
        return result

    def _to_execution_result(
        self,
        extracted_result: ExtractionResult,
        ocr_confidence: float,
        warnings: List[str],
    ) -> ExecutionResult:
        """Convert extraction model object to backward-compatible execution result."""
        extracted_data = {
            field.name: field.value
            for field in extracted_result.fields
            if field.value is not None
        }

        return ExecutionResult(
            extracted_data=extracted_data,
            extracted_result=extracted_result,
            source="ocr_extractor",
            ocr_confidence=ocr_confidence,
            extraction_confidence=extracted_result.overall_quality.value,
            execution_time_seconds=0.0,
            warnings=warnings,
            document_type=extracted_result.recognized_doc_type.value,
            extracted_successfully=extracted_result.extracted_successfully,
        )

    def _build_engine_fallback_result(
        self,
        error_message: str,
        ocr_confidence: float,
    ) -> ExecutionResult:
        """Create a non-crashing engine fallback when OCR step fails."""
        fallback_extraction = ExtractionResult(
            recognized_doc_type=DocumentType.UNKNOWN,
            fields=[],
            overall_quality=ExtractionConfidence.LOW,
            extracted_successfully=False,
            analysis_notes=error_message,
            raw_claude_response="",
        )

        return ExecutionResult(
            extracted_data={},
            extracted_result=fallback_extraction,
            source="ocr_extractor",
            ocr_confidence=ocr_confidence,
            extraction_confidence=ExtractionConfidence.LOW.value,
            execution_time_seconds=0.0,
            warnings=[error_message],
            document_type=DocumentType.UNKNOWN.value,
            extracted_successfully=False,
        )


def extract_from_image(
    image_path: str,
    doc_type_hint: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
) -> ExecutionResult:
    """Convenience function for extraction from image."""
    engine = ExecutionEngine(anthropic_api_key=anthropic_api_key)
    return engine.extract_from_image(image_path=image_path, doc_type_hint=doc_type_hint)


def extract_from_text(
    ocr_text: str,
    doc_type_hint: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
) -> ExecutionResult:
    """Convenience function for extraction from text."""
    engine = ExecutionEngine(anthropic_api_key=anthropic_api_key)
    return engine.extract_from_text(ocr_text=ocr_text, doc_type_hint=doc_type_hint)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python execution_engine_v2.py <image_path> [doc_type_hint]")
        sys.exit(1)

    image_path = sys.argv[1]
    doc_type_hint = sys.argv[2] if len(sys.argv) > 2 else None

    result = extract_from_image(image_path=image_path, doc_type_hint=doc_type_hint)

    print("=" * 70)
    print("Execution Engine v2 Result")
    print("=" * 70)
    print(f"Source: {result.source}")
    print(f"Document type: {result.document_type}")
    print(f"Extraction successful: {result.extracted_successfully}")
    print(f"Execution time: {result.execution_time_seconds:.2f}s")
    print(f"OCR confidence: {result.ocr_confidence:.1%}")
    print(f"Extraction confidence: {result.extraction_confidence}")

    print("\nExtracted data:")
    for key, value in result.extracted_data.items():
        print(f"  {key}: {value}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")
