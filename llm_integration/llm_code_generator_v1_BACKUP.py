"""
LLM Code Generator: Uses Claude API to generate extraction scripts
Generates Python cleanup functions + Pydantic schemas for data extraction
"""

import os
import re
import json
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass

import anthropic


@dataclass
class GeneratedScript:
    """Generated extraction script with schema"""
    script_code: str  # Python cleanup function
    schema_code: str  # Pydantic model
    fields: List[str]  # Extracted field names
    confidence: float  # Claude's confidence (0-1)
    explanation: str  # Why this structure works


class LLMCodeGenerator:
    """
    Generates extraction scripts using Claude API.
    
    Claude writes Python code that:
    1. Parses OCR text using domain knowledge
    2. Returns a Pydantic-validated dict
    3. Has error handling for missing fields
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude API client.
        
        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. "
                "Set it with: export ANTHROPIC_API_KEY=sk-..."
            )
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-opus-4-20250514"  # Use latest Claude model

    def generate_cleanup_script(
        self,
        ocr_text: str,
        doc_type: str,
        confidence_threshold: float = 0.70
    ) -> GeneratedScript:
        """
        Generate an extraction script for the given OCR text.
        
        Claude analyzes the document structure and generates:
        1. A cleanup() function that extracts fields
        2. A Pydantic model that validates the extracted data
        
        Args:
            ocr_text: Full OCR extracted text
            doc_type: Document type (e.g., "kyc_handwritten", "bank_statement")
            confidence_threshold: Min confidence for extracted fields
            
        Returns:
            GeneratedScript with Python code and schema
        """
        # Step 1: Analyze document structure with Claude
        field_analysis = self._analyze_document_structure(ocr_text, doc_type)
        
        # Step 2: Generate Pydantic schema
        schema_code = self._generate_pydantic_schema(
            fields=field_analysis["fields"],
            doc_type=doc_type
        )
        
        # Step 3: Generate cleanup function
        script_code = self._generate_cleanup_function(
            ocr_text=ocr_text,
            fields=field_analysis["fields"],
            doc_type=doc_type
        )
        
        return GeneratedScript(
            script_code=script_code,
            schema_code=schema_code,
            fields=field_analysis["fields"],
            confidence=field_analysis["confidence"],
            explanation=field_analysis["explanation"]
        )

    def _analyze_document_structure(self, ocr_text: str, doc_type: str) -> Dict:
        """
        Use Claude to analyze the document structure and identify fields.
        
        Args:
            ocr_text: Full OCR text
            doc_type: Document type
            
        Returns:
            Dict with fields, confidence, and explanation
        """
        prompt = f"""Analyze this OCR-extracted document and identify the key fields to extract.

Document Type: {doc_type}

OCR Text:
```
{ocr_text[:2000]}
```

Your task:
1. Identify 3-10 key fields present in this document
2. Rate your confidence (0-1) that you can reliably extract these fields
3. Explain the document structure

IMPORTANT: Respond in this exact JSON format, nothing else:
{{
    "fields": ["field1", "field2", "field3"],
    "confidence": 0.85,
    "explanation": "This document appears to be a bank statement with..."
}}

Field names must be:
- Lowercase
- Snake_case (no spaces)
- Descriptive (e.g., "account_number", "transaction_date", "balance")
"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract JSON from response
        response_text = message.content[0].text
        
        try:
            # Find JSON in the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                return {
                    "fields": analysis.get("fields", []),
                    "confidence": analysis.get("confidence", 0.5),
                    "explanation": analysis.get("explanation", "")
                }
        except json.JSONDecodeError:
            pass

        # Fallback: generic fields
        return {
            "fields": ["field_1", "field_2", "field_3"],
            "confidence": 0.5,
            "explanation": "Could not analyze document structure"
        }

    def _generate_pydantic_schema(self, fields: List[str], doc_type: str) -> str:
        """
        Generate a Pydantic model for the extracted fields.
        
        Args:
            fields: List of field names to extract
            doc_type: Document type
            
        Returns:
            Python code for Pydantic model
        """
        prompt = f"""Generate a Pydantic model for extracting fields from a {doc_type} document.

Fields to extract: {', '.join(fields)}

Requirements:
1. Create a class that inherits from BaseModel
2. Use appropriate field types (str, int, float, date, etc.)
3. Make fields optional if they might not always be present
4. Add field descriptions
5. Include validation if needed

Return ONLY the Python code, no explanation.
Start with "from pydantic import BaseModel" and include all imports.
The class should be named with CamelCase based on doc_type.
"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        schema_code = message.content[0].text.strip()
        
        # Ensure imports are present
        if "from pydantic import" not in schema_code:
            schema_code = "from pydantic import BaseModel, Field\nfrom typing import Optional\nfrom datetime import date\n\n" + schema_code

        return schema_code

    def _generate_cleanup_function(
        self,
        ocr_text: str,
        fields: List[str],
        doc_type: str
    ) -> str:
        """
        Generate a cleanup function that extracts fields from OCR text.
        
        Args:
            ocr_text: Full OCR text
            fields: List of field names to extract
            doc_type: Document type
            
        Returns:
            Python code for cleanup function
        """
        prompt = f"""Generate a Python function that extracts fields from OCR text of a {doc_type} document.

Fields to extract: {', '.join(fields)}

Sample OCR text:
```
{ocr_text[:1500]}
```

Requirements:
1. Function signature: def cleanup(ocr_text: str) -> dict:
2. Parse the OCR text to extract the specified fields
3. Return a dict with the extracted values
4. Handle missing fields gracefully (return None or empty string)
5. Clean up text (strip whitespace, normalize dates, etc.)
6. Do NOT import anything - assume ocr_text is already available

Important:
- Use string operations (split, find, strip) to parse the text
- Look for patterns specific to this document type
- Return a dict with keys matching the field names
- Handle common OCR errors (e.g., 0 vs O, 1 vs l)

Return ONLY the function code, nothing else. Start with "def cleanup(ocr_text: str) -> dict:"
"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        cleanup_code = message.content[0].text.strip()
        
        # Ensure proper formatting
        if not cleanup_code.startswith("def cleanup"):
            cleanup_code = "def cleanup(ocr_text: str) -> dict:\n    " + cleanup_code

        return cleanup_code

    def generate_schema_normalize_script(
        self,
        input_columns: List[str],
        sample_rows: List[Dict],
        schema,
    ) -> GeneratedScript:
        """
        Generate a normalize(df) -> pd.DataFrame function that maps heterogeneous
        real-world input into the canonical schema defined by a CanonicalSchema.

        `schema` is a CanonicalSchema from src.canonical_schemas.
        """
        target_type = schema.target_type
        critical_fields = schema.critical_fields
        nice_fields = schema.nice_fields
        enum_hints = schema.enum_hints
        date_fields = schema.date_fields

        all_canonical = critical_fields + nice_fields

        prompt = f"""You are generating a Python function that normalizes bank KYC data
into a strictly defined canonical schema.

TARGET DATASET TYPE: {target_type}

CRITICAL FIELDS (must be mapped whenever the source contains the information):
{json.dumps(critical_fields, indent=2)}

NICE-TO-HAVE FIELDS (map if source has them; return None otherwise):
{json.dumps(nice_fields, indent=2)}

ENUM NORMALIZATIONS (output values must belong to these sets when the field is one of the keys):
{json.dumps(enum_hints, indent=2) if enum_hints else "(none)"}

DATE FIELDS (output format must be YYYY-MM-DD string, or None if unparseable):
{json.dumps(date_fields, indent=2)}

INPUT COLUMNS OBSERVED IN THE SOURCE DATAFRAME:
{json.dumps(input_columns, indent=2)}

SAMPLE INPUT ROWS (first {len(sample_rows)}):
{json.dumps(sample_rows, indent=2, default=str)}

REAL-WORLD MAPPING RULES you MUST apply:

1. Customer name assembly:
   - If source has first_name + last_name → concatenate with space
   - If source has full_name OR name → use as-is
   - If format is "Last, First" → reorder to "First Last"
   - PRESERVE unicode characters: "Jöhn Døe" stays "Jöhn Døe", NEVER strip accents
   - Strip ONLY leading/trailing whitespace, never internal characters

2. Entity / customer type vocabulary (when target field is entity_type):
   - "INDV" | "IND" | "INDIVIDUAL" | "individual" | "person" | "natural person" → "INDIVIDUAL"
   - "CORP" | "CORPORATE" | "Corp." | "Company" | "LE" | "LEGAL_ENTITY" → "LEGAL_ENTITY"

3. Risk rating vocabulary (when target field is risk_rating):
   - "Low" | "LOW" | "LOW_RISK" | "L" | "Tier 1" → "LOW"
   - "Med" | "Medium" | "MEDIUM" | "M" | "Tier 2" → "MEDIUM"
   - "High" | "HIGH" | "HIGH_RISK" | "H" | "Tier 3" → "HIGH"

4. AML screening result vocabulary (when target field is screening_result):
   - "No hits found" | "NO_HIT" | "NO_HIT_CURRENT" | "Clear" | "clean" | "OK" | "PASS" → "NO_MATCH"
   - "Hit" | "Match" | "Possible Match" | "HIT_CURRENT" → "MATCH"

5. Hit status vocabulary (when target field is hit_status):
   - "confirmed" | "true match" | "CONFIRMED" → "CONFIRMED"
   - "false positive" | "FP" | "cleared" → "FALSE_POSITIVE"
   - "under review" | "REVIEW" | "pending" → "UNDER_REVIEW"

6. Document type vocabulary (when target field is document_type under id_verifications):
   - "Passport" | "PP" | "passport" → "PASSPORT"
   - "NatID" | "National ID" | "Nat ID" | "Nat. ID Card" → "NATIONAL_ID"
   - "DL" | "Driver's Licence" | "Drivers License" | "Driver License" → "DRIVERS_LICENSE"
   - "State ID" | "State Identification" → "STATE_ID"
   - "Residence Permit" | "RP" → "RESIDENCE_PERMIT"

7. Document type vocabulary (when target field is document_type under documents / PoA):
   - "Utility Bill" | "utility bill" | "UTILITY" | "Bank stm." (misc abbreviation) → map sensibly
   - "Bank Statement" | "Bank Stmt" | "Bank stm." → "BANK_STATEMENT"
   - "Utility Bill" | "Electric bill" | "Water bill" → "UTILITY_BILL"
   - "Lease" | "Lease Agreement" | "Lease agrmt" | "Rental Agreement" → "LEASE_AGREEMENT"
   - "Council Tax Bill" → "COUNCIL_TAX_BILL"
   - "Tax Notice" | "Tax Bill" → "TAX_NOTICE"
   - "Insurance" | "Insurance Certificate" → "INSURANCE_CERTIFICATE"
   - Unknown types → "OTHER"

8. Document category (documents dataset only): all proof-of-address documents
   must produce document_category = "POA"

9. Document status (id_verifications):
   - "APPROVED" | "Verified" | "valid" → "VERIFIED"
   - "expired" | "EXPIRED" | "lapsed" → "EXPIRED"
   - "pending" | "in review" → "PENDING"
   - "rejected" | "declined" | "manual override" → "REJECTED"

10. Date parsing — handle ALL these formats, output YYYY-MM-DD:
    - ISO: "2024-01-20", "2024-01-20T14:30:00Z"
    - US slash: "01/20/2024", "1/20/24"
    - EU slash: "20/01/2024"
    - Dashes: "20-01-2024", "01-20-24"
    - Two-digit years: "08-22-85" → assume 1900s if year > current 2-digit year, else 2000s
    - Natural language: "Aug 22 2023", "22 Aug 2023", "August 22, 2023"
    - If genuinely unparseable, return None. NEVER guess a date.
    - You may `from datetime import datetime` inside the function body.

STRICT PROHIBITIONS:
- Do NOT invent values for fields missing from the source. Return None.
- Do NOT drop rows. Every input row must produce exactly one output row.
- Do NOT modify customer_id values. Preserve them exactly as given.
- Do NOT strip unicode characters from names or other text fields.
- Do NOT collapse rows that share a customer_id. One row in → one row out.

OUTPUT CONTRACT:
- Function signature: def normalize(df):
- Returns a pandas DataFrame with EXACTLY these columns (all of them, in any order):
  {json.dumps(all_canonical)}
- pandas is available as `pd`. You may import from Python stdlib inside the function body.
- Return ONLY raw Python code. No markdown fences. No explanation. No preamble.
- First characters of your response must be: def normalize(df):
"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=(
                "You are a Python code generator specializing in bank data normalization. "
                "You write defensive pandas code that handles real-world schema drift, "
                "vocabulary variance, and format inconsistency. You never invent data, "
                "never drop rows, and never strip unicode from text. "
                "Return ONLY raw Python code — no explanation, no markdown, no backticks."
            ),
            messages=[{"role": "user", "content": prompt}],
        )

        script_code = message.content[0].text.strip()

        # Strip markdown fences if present
        if script_code.startswith("```"):
            lines = script_code.split("\n")
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            script_code = "\n".join(lines).strip()

        # Trim preamble before `def normalize`
        idx = script_code.find("def normalize")
        if idx > 0:
            script_code = script_code[idx:]

        try:
            compile(script_code, "<normalize>", "exec")
        except SyntaxError as e:
            raise RuntimeError(
                f"Generated normalize script has syntax error: {e}\n\nCode:\n{script_code}"
            )

        return GeneratedScript(
            script_code=script_code,
            schema_code="",
            fields=all_canonical,
            confidence=0.90,
            explanation=f"Schema normalizer for {target_type}",
        )

    def validate_generated_script(self, script: GeneratedScript) -> Tuple[bool, str]:
        """
        Validate that generated script is syntactically correct.
        
        Args:
            script: Generated script to validate
            
        Returns:
            (is_valid, error_message)
        """
        try:
            # Try to compile the cleanup function
            compile(script.script_code, '<string>', 'exec')
            
            # Try to compile the schema
            compile(script.schema_code, '<string>', 'exec')
            
            # Check that cleanup function exists
            if "def cleanup(ocr_text: str)" not in script.script_code:
                return False, "cleanup() function not found in generated code"
            
            # Check that schema is a Pydantic BaseModel
            if "BaseModel" not in script.schema_code:
                return False, "BaseModel class not found in schema"
            
            return True, ""
        
        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"


def generate_cleanup_script(
    ocr_text: str,
    doc_type: str,
    api_key: Optional[str] = None
) -> GeneratedScript:
    """Convenience function to generate a cleanup script"""
    generator = LLMCodeGenerator(api_key=api_key)
    return generator.generate_cleanup_script(ocr_text, doc_type)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python llm_code_generator.py <doc_type> [ocr_text_file]")
        print("Example: python llm_code_generator.py kyc_handwritten sample.txt")
        sys.exit(1)

    doc_type = sys.argv[1]
    
    # Read sample OCR text
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'r') as f:
            ocr_text = f.read()
    else:
        # Default sample
        ocr_text = """NORTHEAST ATLANTIC RETAIL BANK
Statement Date: 2025-03-15
Luis Romero
124 East 74th Street, Apt 5B
New York, NY 10021
USA
PERSONAL CHECKING ACCOUNT STATEMENT
Account Number: **** 6789"""

    print("=" * 60)
    print(f"Generating cleanup script for: {doc_type}")
    print("=" * 60)

    try:
        generator = LLMCodeGenerator()
        script = generator.generate_cleanup_script(ocr_text, doc_type)

        print("\nGenerated Fields:", script.fields)
        print(f"Confidence: {script.confidence:.1%}")
        print(f"\nExplanation:\n{script.explanation}")

        # Validate
        is_valid, error = generator.validate_generated_script(script)
        print(f"\nValidation: {' PASS' if is_valid else ' FAIL'}")
        if error:
            print(f"Error: {error}")

        print("\n" + "=" * 60)
        print("Generated Pydantic Schema:")
        print("=" * 60)
        print(script.schema_code)

        print("\n" + "=" * 60)
        print("Generated Cleanup Function:")
        print("=" * 60)
        print(script.script_code)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
