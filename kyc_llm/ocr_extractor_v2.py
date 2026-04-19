"""OCR extraction v2: structured Claude JSON extraction with robust fallbacks."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import anthropic


class DocumentType(str, Enum):
    """Recognized document types."""

    PASSPORT = "passport"
    NATIONAL_ID = "national_id"
    DRIVER_LICENSE = "driver_license"
    STUDENT_ID = "student_id"
    BANK_STATEMENT = "bank_statement"
    UTILITY_BILL = "utility_bill"
    CERTIFICATE_OF_INCORPORATION = "certificate_of_incorporation"
    LEASE_AGREEMENT = "lease_agreement"
    UNKNOWN = "unknown"


class ExtractionConfidence(str, Enum):
    """Extraction confidence levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOT_FOUND = "not_found"


@dataclass
class ExtractedField:
    """Single extracted field with field-level confidence."""

    name: str
    value: Optional[str]
    confidence: ExtractionConfidence
    notes: Optional[str] = None


@dataclass
class ExtractionResult:
    """Complete extraction result from OCR text."""

    recognized_doc_type: DocumentType
    fields: List[ExtractedField]
    overall_quality: ExtractionConfidence
    extracted_successfully: bool
    analysis_notes: str
    raw_claude_response: str

    def to_dict(self) -> Dict:
        """Serialize extraction result as a plain dictionary."""
        return {
            "recognized_doc_type": self.recognized_doc_type.value,
            "fields": [
                {
                    "name": field.name,
                    "value": field.value,
                    "confidence": field.confidence.value,
                    "notes": field.notes,
                }
                for field in self.fields
            ],
            "overall_quality": self.overall_quality.value,
            "extracted_successfully": self.extracted_successfully,
            "analysis_notes": self.analysis_notes,
            "raw_claude_response": self.raw_claude_response,
        }

    def get_field(self, field_name: str) -> Optional[str]:
        """Return field value for a specific field name if present."""
        for field in self.fields:
            if field.name == field_name:
                return field.value
        return None

    def get_high_confidence_fields(self) -> Dict[str, str]:
        """Return only fields extracted with high confidence and non-empty values."""
        high_conf_fields: Dict[str, str] = {}
        for field in self.fields:
            if field.confidence == ExtractionConfidence.HIGH and field.value:
                high_conf_fields[field.name] = field.value
        return high_conf_fields


class OCRExtractor:
    """Main extractor that performs one Claude call and parses structured JSON."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Anthropic client from explicit key or ANTHROPIC_API_KEY."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = "claude-opus-4-20250514"
        self.initialization_error: Optional[str] = None

        if not self.api_key:
            self.client = None
            self.initialization_error = (
                "ANTHROPIC_API_KEY not set. Provide api_key or export ANTHROPIC_API_KEY."
            )
            return

        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except Exception as exc:
            self.client = None
            self.initialization_error = f"Failed to initialize Anthropic client: {exc}"

    def extract_from_ocr_text(
        self,
        ocr_text: str,
        hint_doc_type: Optional[str] = None,
    ) -> ExtractionResult:
        """Extract structured data from OCR text in a single Claude request."""
        if not ocr_text or not ocr_text.strip():
            return self._create_fallback_result(ocr_text, "OCR text is empty.")

        if self.initialization_error or self.client is None:
            return self._create_fallback_result(
                ocr_text,
                self.initialization_error or "Anthropic client is unavailable.",
            )

        prompt = self._build_extraction_prompt(ocr_text=ocr_text, hint_doc_type=hint_doc_type)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as exc:
            return self._create_fallback_result(
                ocr_text,
                f"Anthropic API error during extraction: {exc}",
            )
        except Exception as exc:
            return self._create_fallback_result(
                ocr_text,
                f"Unexpected extraction call error: {exc}",
            )

        raw_response_parts: List[str] = []
        for block in getattr(message, "content", []):
            text = getattr(block, "text", None)
            if text:
                raw_response_parts.append(text)
        raw_response = "\n".join(raw_response_parts).strip()

        if not raw_response:
            return self._create_fallback_result(ocr_text, "Claude returned an empty response.")

        return self._parse_extraction_response(raw_response=raw_response, ocr_text=ocr_text)

    def _build_extraction_prompt(self, ocr_text: str, hint_doc_type: Optional[str]) -> str:
        """Build strict JSON-only extraction prompt."""
        hint_text = ""
        if hint_doc_type:
            hint_text = (
                "Document type hint from upstream system: "
                f"'{hint_doc_type}'. Use this as a hint only if OCR evidence supports it."
            )

        return f"""You are an OCR data extraction specialist. Your job is to analyze OCR text and extract structured data.

{hint_text}

OCR TEXT:
```
{ocr_text[:12000]}
```

TASK:
1. Identify what type of document this is
2. Extract all visible fields and values
3. Rate your confidence in each extraction
4. Note any quality issues

IMPORTANT: Respond with ONLY valid JSON. No preamble, no markdown.

Response format:
{{
    "document_type": "one of: passport, national_id, driver_license, student_id, bank_statement, utility_bill, certificate_of_incorporation, lease_agreement, unknown",
    "fields": [
        {{
            "name": "field_name",
            "value": "extracted_value_or_null",
            "confidence": "high|medium|low|not_found"
        }}
    ],
    "overall_quality": "high|medium|low",
    "extraction_successful": true,
    "notes": "Any observations"
}}

Common field guidance by type:
- passport: name, passport_number, nationality, date_of_birth, expiry_date
- national_id: full_name, id_number, date_of_birth, address, issue_date
- driver_license: full_name, license_number, class, issue_date, expiry_date
- student_id: name, student_id, institution, program, valid_thru
- bank_statement: account_holder, account_number, statement_period, opening_balance, closing_balance
- utility_bill: account_name, service_address, billing_period, amount_due, due_date
- certificate_of_incorporation: company_name, registration_number, incorporation_date, jurisdiction
- lease_agreement: tenant_name, landlord_name, property_address, lease_start, lease_end, monthly_rent
"""

    def _parse_extraction_response(self, raw_response: str, ocr_text: str) -> ExtractionResult:
        """Parse Claude response JSON and normalize into `ExtractionResult`."""
        cleaned = raw_response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        parsed: Dict
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # Best-effort extraction when model includes extra text around JSON.
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                return self._create_fallback_result(
                    ocr_text,
                    "Failed to parse Claude response as JSON.",
                    raw_claude_response=raw_response,
                )
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return self._create_fallback_result(
                    ocr_text,
                    "Failed to parse Claude response JSON object after cleanup.",
                    raw_claude_response=raw_response,
                )

        try:
            normalized_doc_type = self._normalize_doc_type(str(parsed.get("document_type", "unknown")))
            overall_quality = self._normalize_confidence(str(parsed.get("overall_quality", "low")))
            extracted_successfully = bool(parsed.get("extraction_successful", False))
            notes = str(parsed.get("notes", ""))

            raw_fields = parsed.get("fields", [])
            fields: List[ExtractedField] = []
            if isinstance(raw_fields, list):
                for item in raw_fields:
                    if not isinstance(item, dict):
                        continue

                    field_name = str(item.get("name", "")).strip()
                    if not field_name:
                        continue

                    raw_value = item.get("value")
                    value = None if raw_value in [None, "null", "None"] else str(raw_value).strip()
                    if value == "":
                        value = None

                    field_confidence = self._normalize_confidence(str(item.get("confidence", "not_found")))
                    field_notes = item.get("notes")
                    notes_value = str(field_notes).strip() if field_notes is not None else None

                    fields.append(
                        ExtractedField(
                            name=field_name,
                            value=value,
                            confidence=field_confidence,
                            notes=notes_value,
                        )
                    )

            if not fields:
                fields = [
                    ExtractedField(
                        name="raw_ocr_text",
                        value=ocr_text[:500],
                        confidence=ExtractionConfidence.LOW,
                        notes="No structured fields parsed from response.",
                    )
                ]

            return ExtractionResult(
                recognized_doc_type=normalized_doc_type,
                fields=fields,
                overall_quality=overall_quality,
                extracted_successfully=extracted_successfully,
                analysis_notes=notes,
                raw_claude_response=raw_response,
            )
        except Exception as exc:
            return self._create_fallback_result(
                ocr_text,
                f"Failed to normalize extraction response: {exc}",
                raw_claude_response=raw_response,
            )

    def _normalize_doc_type(self, doc_type_str: str) -> DocumentType:
        """Normalize document type string into `DocumentType` enum."""
        normalized = doc_type_str.strip().lower()
        exact_map = {doc.value: doc for doc in DocumentType}
        if normalized in exact_map:
            return exact_map[normalized]

        fuzzy_tokens = {
            "passport": DocumentType.PASSPORT,
            "national": DocumentType.NATIONAL_ID,
            "id": DocumentType.NATIONAL_ID,
            "driver": DocumentType.DRIVER_LICENSE,
            "license": DocumentType.DRIVER_LICENSE,
            "student": DocumentType.STUDENT_ID,
            "bank": DocumentType.BANK_STATEMENT,
            "statement": DocumentType.BANK_STATEMENT,
            "utility": DocumentType.UTILITY_BILL,
            "bill": DocumentType.UTILITY_BILL,
            "incorporation": DocumentType.CERTIFICATE_OF_INCORPORATION,
            "certificate": DocumentType.CERTIFICATE_OF_INCORPORATION,
            "lease": DocumentType.LEASE_AGREEMENT,
            "rental": DocumentType.LEASE_AGREEMENT,
        }
        for token, doc_type in fuzzy_tokens.items():
            if token in normalized:
                return doc_type

        return DocumentType.UNKNOWN

    def _normalize_confidence(self, conf_str: str) -> ExtractionConfidence:
        """Normalize confidence strings into `ExtractionConfidence` values."""
        normalized = conf_str.strip().lower().replace("-", "_")

        if normalized in {"high", "h"}:
            return ExtractionConfidence.HIGH
        if normalized in {"medium", "med", "m"}:
            return ExtractionConfidence.MEDIUM
        if normalized in {"low", "l"}:
            return ExtractionConfidence.LOW
        if normalized in {"not_found", "not found", "missing", "none", "n/a"}:
            return ExtractionConfidence.NOT_FOUND

        return ExtractionConfidence.LOW

    def _create_fallback_result(
        self,
        ocr_text: str,
        error_message: str,
        raw_claude_response: str = "",
    ) -> ExtractionResult:
        """Create robust fallback result for any extraction or parsing failure."""
        return ExtractionResult(
            recognized_doc_type=DocumentType.UNKNOWN,
            fields=[
                ExtractedField(
                    name="raw_ocr_text",
                    value=(ocr_text or "")[:500],
                    confidence=ExtractionConfidence.HIGH,
                    notes="Fallback",
                )
            ],
            overall_quality=ExtractionConfidence.LOW,
            extracted_successfully=False,
            analysis_notes=error_message,
            raw_claude_response=raw_claude_response,
        )


def extract_from_ocr_text(
    ocr_text: str,
    hint_doc_type: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ExtractionResult:
    """Convenience function for one-off OCR extraction requests."""
    extractor = OCRExtractor(api_key=api_key)
    return extractor.extract_from_ocr_text(ocr_text=ocr_text, hint_doc_type=hint_doc_type)


if __name__ == "__main__":
    sample_student_id_ocr = """
    APEXON UNIVERSITY
    STUDENT ID CARD
    Name: Luis Romero
    Student ID: S10293847
    Program: Computer Science
    Status: UNDERGRADUATE
    Valid Thru: 2027-06-30
    """

    print("=" * 70)
    print("OCR Extractor v2 - Standalone Test")
    print("=" * 70)

    try:
        result = extract_from_ocr_text(
            ocr_text=sample_student_id_ocr,
            hint_doc_type="student_id",
        )

        print("\nDetected document type:", result.recognized_doc_type.value)
        print("Overall quality:", result.overall_quality.value)
        print("Extraction successful:", result.extracted_successfully)

        print("\nExtracted fields:")
        for field in result.fields:
            print(
                f"  - {field.name}: {field.value} "
                f"(confidence={field.confidence.value}, notes={field.notes})"
            )

        print("\nHigh confidence fields:")
        print(json.dumps(result.get_high_confidence_fields(), indent=2))

        print("\nFull JSON:")
        print(json.dumps(result.to_dict(), indent=2))
    except Exception as exc:
        print(f"Standalone test failed: {exc}")
