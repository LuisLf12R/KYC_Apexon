"""
Test script for OCR Handler
Run this to verify Google Vision API setup before building downstream modules
"""

import os
import sys
from pathlib import Path

# Add llm_integration to path
sys.path.insert(0, str(Path(__file__).parent))

from llm_integration import OCRHandler, ocr_from_file


def test_ocr_setup():
    """Test 1: Verify Google Vision client initializes"""
    print("=" * 60)
    print("TEST 1: Google Vision API Setup")
    print("=" * 60)
    
    creds_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_env:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS not set")
        print("   Set it with: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json")
        return False
    
    print(f"✅ GOOGLE_APPLICATION_CREDENTIALS set: {creds_env}")
    
    try:
        handler = OCRHandler()
        print("✅ Google Vision client initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize Google Vision client: {e}")
        return False


def test_ocr_with_sample(image_path: str):
    """Test 2: Extract text from a real image"""
    print("\n" + "=" * 60)
    print(f"TEST 2: OCR Extraction from {image_path}")
    print("=" * 60)
    
    if not Path(image_path).exists():
        print(f"❌ Image file not found: {image_path}")
        print("   Provide a real handwritten document image to test")
        return False
    
    try:
        result = ocr_from_file(image_path)
        
        print(f"✅ OCR completed successfully")
        print(f"\n   Full Text ({len(result.full_text)} chars):")
        print(f"   {result.full_text[:200]}..." if len(result.full_text) > 200 else f"   {result.full_text}")
        
        print(f"\n   Confidence: {result.confidence:.1%}")
        print(f"   Language: {result.language}")
        print(f"   Text blocks detected: {result.detected_fields['block_count']}")
        print(f"   Handwritten regions: {result.detected_fields['handwriting_regions']}")
        print(f"   Printed regions: {result.detected_fields['printed_regions']}")
        
        if result.warnings:
            print(f"\n   ⚠️  Warnings:")
            for w in result.warnings:
                print(f"      - {w}")
        
        return True
    except Exception as e:
        print(f"❌ OCR extraction failed: {e}")
        return False


def test_ocr_output_format(image_path: str):
    """Test 3: Verify output format matches expected schema"""
    print("\n" + "=" * 60)
    print("TEST 3: Output Format Validation")
    print("=" * 60)
    
    if not Path(image_path).exists():
        print(f"⏭️  Skipping (image file not found)")
        return True
    
    try:
        result = ocr_from_file(image_path)
        
        # Check required fields
        required_fields = ["full_text", "confidence", "detected_fields", "warnings", "language"]
        missing = [f for f in required_fields if not hasattr(result, f)]
        
        if missing:
            print(f"❌ Missing fields: {missing}")
            return False
        
        print("✅ All required fields present")
        
        # Check detected_fields structure
        expected_subfields = ["text_blocks", "handwriting_regions", "printed_regions", "language", "block_count"]
        missing_sub = [f for f in expected_subfields if f not in result.detected_fields]
        
        if missing_sub:
            print(f"❌ Missing detected_fields: {missing_sub}")
            return False
        
        print("✅ detected_fields structure valid")
        
        # Verify types
        assert isinstance(result.full_text, str), "full_text should be str"
        assert isinstance(result.confidence, float), "confidence should be float"
        assert 0 <= result.confidence <= 1, "confidence should be 0-1"
        assert isinstance(result.detected_fields, dict), "detected_fields should be dict"
        assert isinstance(result.warnings, list), "warnings should be list"
        
        print("✅ All field types correct")
        
        return True
    except Exception as e:
        print(f"❌ Format validation failed: {e}")
        return False


def main():
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " OCR Handler Module Test Suite ".center(58) + "║")
    print("╚" + "=" * 58 + "╝")
    
    # Test 1: Setup
    setup_ok = test_ocr_setup()
    if not setup_ok:
        print("\n❌ Setup test failed. Cannot continue.")
        return 1
    
    # Test 2 & 3: Ask for sample image
    sample_image = input("\nEnter path to a handwritten document image (or press Enter to skip extraction tests): ").strip()
    
    if sample_image:
        extraction_ok = test_ocr_with_sample(sample_image)
        format_ok = test_ocr_output_format(sample_image)
    else:
        print("\n⏭️  Skipping extraction tests (no image provided)")
        extraction_ok = True
        format_ok = True
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    all_ok = setup_ok and extraction_ok and format_ok
    
    if all_ok:
        print("✅ All tests passed! OCR module is ready.")
        print("\nNext steps:")
        print("  1. Test with your own document image")
        print("  2. Move to script_cache_manager.py")
        return 0
    else:
        print("❌ Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
