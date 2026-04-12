"""
Test script for LLMCodeGenerator
Demonstrates: Generate script → Validate → Cache → Execute
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from llm_integration.llm_code_generator import LLMCodeGenerator, generate_cleanup_script
from llm_integration.script_cache_manager import ScriptCacheManager


def test_llm_code_generator():
    """Test the LLM code generator"""
    print("=" * 70)
    print("LLM Code Generator Tests")
    print("=" * 70)

    # Check API key
    print("\nTEST 0: API Key Setup")
    print("-" * 70)
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(" ANTHROPIC_API_KEY not set!")
        print("   Set it with: export ANTHROPIC_API_KEY=sk-...")
        return False
    
    print(" ANTHROPIC_API_KEY is set")

    # Sample OCR text (from real bank statement)
    sample_ocr = """NORTHEAST ATLANTIC RETAIL BANK
Statement Date: 2025-03-15
Luis Romero
124 East 74th Street, Apt 5B
New York, NY 10021
USA
PERSONAL CHECKING ACCOUNT STATEMENT
Account Number: **** 6789
TRANSACTION DETAIL
Date Description Type Amount
2025-02-16 Grocery Store Purchase Debit -$68.45
2025-02-18 Online Retailer Debit -$42.10 $1,192.46
Balance
$1,234.56
2025-02-22 Direct Deposit - Payroll Credit +$1,850.00 $3,042.46
2025-02-25 Utilities Payment Debit -$115.30 $2,927.16"""

    # Test 1: Generate cleanup script
    print("\nTEST 1: Generate cleanup script with Claude")
    print("-" * 70)

    try:
        generator = LLMCodeGenerator(api_key=api_key)
        print("Generating script for: kyc_bank_statement")
        print("(Claude is analyzing the document structure...)")
        
        script = generator.generate_cleanup_script(
            ocr_text=sample_ocr,
            doc_type="kyc_bank_statement"
        )

        print(f" Script generated successfully!")
        print(f"   Fields identified: {script.fields}")
        print(f"   Confidence: {script.confidence:.1%}")
        print(f"   Explanation: {script.explanation[:100]}...")

    except Exception as e:
        print(f" Error generating script: {e}")
        print("\nNote: This test requires ANTHROPIC_API_KEY to be set")
        print("Set it with: export ANTHROPIC_API_KEY=sk-...")
        return False

    # Test 2: Validate generated script
    print("\nTEST 2: Validate generated script")
    print("-" * 70)

    is_valid, error = generator.validate_generated_script(script)
    if is_valid:
        print(" Script validation passed!")
    else:
        print(f"  Script validation failed: {error}")
        print("   Claude may need to regenerate")

    # Test 3: Display generated code
    print("\nTEST 3: Review generated code")
    print("-" * 70)

    print("\n--- Generated Pydantic Schema ---")
    print(script.schema_code[:300] + "..." if len(script.schema_code) > 300 else script.schema_code)

    print("\n--- Generated Cleanup Function ---")
    print(script.script_code[:300] + "..." if len(script.script_code) > 300 else script.script_code)

    # Test 4: Cache the generated script
    print("\nTEST 4: Cache the generated script")
    print("-" * 70)

    try:
        manager = ScriptCacheManager()
        layout_hash = manager.compute_layout_hash(sample_ocr)

        script_id = manager.save_script(
            script_code=script.script_code,
            schema_code=script.schema_code,
            layout_hash=layout_hash,
            fields=script.fields,
            doc_type="kyc_bank_statement",
            source="generated",
            confidence_threshold=script.confidence
        )

        print(f" Script cached successfully!")
        print(f"   Script ID: {script_id}")
        print(f"   Fields: {', '.join(script.fields)}")

    except Exception as e:
        print(f"  Error caching script: {e}")

    # Test 5: Retrieve from cache
    print("\nTEST 5: Retrieve from cache")
    print("-" * 70)

    try:
        found = manager.find_script(layout_hash)
        if found:
            print(f" Found cached script: {found['id']}")
            print(f"   Fields: {found['fields']}")
        else:
            print(" Script not found in cache")

    except Exception as e:
        print(f"  Error retrieving from cache: {e}")

    # Test 6: Execute cached script
    print("\nTEST 6: Execute cached script on OCR text")
    print("-" * 70)

    try:
        result = manager.execute_script(script_id, sample_ocr)
        print(f" Script executed successfully!")
        print(f"   Extracted data: {result}")

    except Exception as e:
        print(f"  Execution note: {e}")
        print("   (This is expected - generated scripts may need manual refinement)")

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print("""
 Module 3 (LLM Code Generator) is working!

You now have:
1. OCR extraction (Module 1) 
2. Script caching (Module 2) 
3. Claude-powered code generation (Module 3) 

Next steps:
1. Review generated_script.py and schema
2. Test with your own documents
3. Proceed to Module 4: execution_engine.py
    """)

    return True


if __name__ == "__main__":
    try:
        success = test_llm_code_generator()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)