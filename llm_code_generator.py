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

    def generate_schema_transform_script(
        self,
        input_columns: List[str],
        sample_rows: List[Dict],
        target_schema: Dict[str, List[str]],
        doc_type: str,
    ) -> "GeneratedScript":
        """
        Generate a schema transformation function using Claude.

        Claude receives the input column names, sample rows, and target schema,
        and writes a Python function that maps input rows to engine-ready tables.

        Args:
            input_columns: List of column names in the input data
            sample_rows: First 3 rows of input data for Claude to inspect
            target_schema: Dict mapping table name -> list of required column names
            doc_type: Identifier used for caching (e.g. "scenario_manifest_to_kyc_tables")

        Returns:
            GeneratedScript with transform function code
        """
        prompt = f"""You are given input data rows with these columns:
{json.dumps(input_columns, indent=2)}

Sample rows (first {len(sample_rows)}):
{json.dumps(sample_rows, indent=2, default=str)}

Write a Python function that transforms a list of these rows into the following target tables:

Target schema (table name -> required columns):
{json.dumps(target_schema, indent=2)}

Rules:
- Function signature must be exactly: def transform(rows: list) -> dict:
- Return a dict where keys are table names and values are lists of row dicts
- Each output row must contain exactly the columns specified for that table
- Use only Python stdlib — no imports inside the function
- Handle None/missing/empty values with safe defaults (empty string or 0)
- Parse all date fields to YYYY-MM-DD string format from ISO or any common format
- Map values sensibly (e.g. risk_tier LOW->Low, aml_state NO_HIT_CURRENT->No Hit)
- Return ONLY the raw function code starting with: def transform(rows: list) -> dict:
"""

        message = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            system=(
                "You are a Python code generator. You write clean, defensive data "
                "transformation functions. Return ONLY raw Python code with no "
                "explanation, no markdown, no backticks."
            ),
            messages=[{"role": "user", "content": prompt}]
        )

        transform_code = message.content[0].text.strip()

        # Strip markdown fences if Claude included them
        if transform_code.startswith("```"):
            lines = transform_code.split("\n")
            transform_code = "\n".join(
                lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
            ).strip()

        # Find the function start if there's preamble
        idx = transform_code.find("def transform")
        if idx > 0:
            transform_code = transform_code[idx:]

        # Validate it compiles
        try:
            compile(transform_code, "<transform>", "exec")
        except SyntaxError as e:
            raise RuntimeError(f"Generated transform script has syntax error: {e}\n\nCode:\n{transform_code}")

        return GeneratedScript(
            script_code=transform_code,
            schema_code="",
            fields=list(target_schema.keys()),
            confidence=0.85,
            explanation=f"Claude-generated schema transform for {doc_type}",
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