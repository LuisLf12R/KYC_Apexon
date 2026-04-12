import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from llm_integration import OCRHandler

print("Testing OCR Handler...")
try:
    handler = OCRHandler()
    print("Success! OCRHandler initialized!")
except Exception as e:
    print(f"Error: {e}")
