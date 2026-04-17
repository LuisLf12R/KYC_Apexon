"""LLM Integration module for OCR-driven extraction workflows.

Provides:
- ocr_handler: Google Vision OCR wrapper
- ocr_extractor_v2: Structured one-step extraction over OCR text
- execution_engine: Default v2 execution engine (OCR -> extractor)
"""

from .ocr_handler import OCRHandler, OCRResult, TextBlock, ocr_from_file, ocr_from_url

__version__ = "0.2.0"
__all__ = [
    "OCRHandler",
    "OCRResult",
    "TextBlock",
    "ocr_from_file",
    "ocr_from_url",
]
