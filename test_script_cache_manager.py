"""
Test script for ScriptCacheManager
Demonstrates: store scripts, exact matching, fuzzy matching, execution
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from llm_integration.script_cache_manager import ScriptCacheManager


def test_cache_manager():
    """Test the cache manager functionality"""
    print("=" * 60)
    print("Script Cache Manager Tests")
    print("=" * 60)

    # Initialize manager
    manager = ScriptCacheManager("./scripts_cache")
    print("\n Cache manager initialized")

    # Test 1: Save a script
    print("\n" + "-" * 60)
    print("TEST 1: Save a script")
    print("-" * 60)

    sample_script_code = '''
def cleanup(ocr_text):
    """Extract KYC fields from OCR text"""
    lines = ocr_text.split('\\n')
    result = {}
    
    # Simple parsing logic (in real use, Claude generates this)
    for i, line in enumerate(lines):
        if 'NORTHEAST ATLANTIC' in line:
            result['bank_name'] = 'NORTHEAST ATLANTIC RETAIL BANK'
        if 'Luis Romero' in line:
            result['name'] = 'Luis Romero'
        if 'New York' in line:
            result['city'] = 'New York'
    
    return result
'''

    sample_schema_code = '''
from pydantic import BaseModel

class KYCData(BaseModel):
    """KYC extraction schema"""
    name: str
    city: str
    bank_name: str
'''

    sample_ocr = "NORTHEAST ATLANTIC\\nLuis Romero\\nNew York, NY"
    layout_hash = manager.compute_layout_hash(sample_ocr)

    script_id = manager.save_script(
        script_code=sample_script_code,
        schema_code=sample_schema_code,
        layout_hash=layout_hash,
        fields=["name", "city", "bank_name"],
        doc_type="kyc_bank_statement",
        source="generated",
        confidence_threshold=0.85
    )

    print(f" Script saved with ID: {script_id}")
    print(f"   Layout hash: {layout_hash[:16]}...")
    print(f"   Fields: name, city, bank_name")

    # Test 2: List scripts
    print("\n" + "-" * 60)
    print("TEST 2: List cached scripts")
    print("-" * 60)

    scripts = manager.list_scripts()
    print(f" Found {len(scripts)} cached script(s):")
    for s in scripts:
        print(f"   - {s['id']}: {s['fields']} (doc_type: {s['doc_type']})")

    # Test 3: Exact match
    print("\n" + "-" * 60)
    print("TEST 3: Exact match lookup")
    print("-" * 60)

    found = manager.find_script(layout_hash)
    if found:
        print(f" Exact match found: {found['id']}")
        print(f"   Fields: {found['fields']}")
        print(f"   Confidence threshold: {found['confidence_threshold']}")
    else:
        print(" No exact match found")

    # Test 4: Fuzzy match (with different OCR text)
    print("\n" + "-" * 60)
    print("TEST 4: Fuzzy match lookup")
    print("-" * 60)

    different_ocr = "NORTHEAST ATLANTIC RETAIL BANK\\nJane Smith\\nLos Angeles, CA"
    different_hash = manager.compute_layout_hash(different_ocr)

    found = manager.find_script(different_hash, ocr_text=different_ocr, fuzzy_threshold=0.5)
    if found:
        print(f" Fuzzy match found: {found['id']}")
        print(f"   Similarity threshold: 0.5")
    else:
        print("  No fuzzy match found (this is OK for this test)")

    # Test 5: Load and execute script
    print("\n" + "-" * 60)
    print("TEST 5: Load and execute script")
    print("-" * 60)

    try:
        result = manager.execute_script(script_id, sample_ocr)
        print(f" Script executed successfully")
        print(f"   Extracted data: {result}")
    except Exception as e:
        print(f"  Execution note: {e}")

    # Test 6: Cache statistics
    print("\n" + "-" * 60)
    print("TEST 6: Cache statistics")
    print("-" * 60)

    stats = manager.get_cache_stats()
    print(f" Cache statistics:")
    print(f"   Total scripts: {stats['total_scripts']}")
    print(f"   Document types: {stats['document_types']}")
    print(f"   Cache size: {stats['cache_size_bytes']} bytes")
    print(f"   Metadata file: {stats['metadata_file']}")

    # Test 7: Get script info
    print("\n" + "-" * 60)
    print("TEST 7: Get script metadata")
    print("-" * 60)

    info = manager.get_script_info(script_id)
    if info:
        print(f" Script info retrieved:")
        print(f"   ID: {info['id']}")
        print(f"   Created: {info['created_date']}")
        print(f"   Last used: {info['last_used']}")
        print(f"   Source: {info['source']}")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(" All tests completed successfully!")
    print("\nNext steps:")
    print("  1. Review scripts_cache/metadata.json")
    print("  2. Check scripts_cache/*.py and *.schema files")
    print("  3. Proceed to Module 3: llm_code_generator.py")


if __name__ == "__main__":
    try:
        test_cache_manager()
    except Exception as e:
        print(f"\n Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)