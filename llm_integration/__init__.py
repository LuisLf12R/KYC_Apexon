"""
LLM Integration Module for RegTech KYC/AML Pipeline

Provides:
- ocr_handler: Google Vision API wrapper
- script_cache_manager: LLM script caching & retrieval
- llm_code_generator: Claude API for script generation
- execution_engine: Safe script execution
"""

from .ocr_handler import (
    OCRHandler,
    OCRResult,
    TextBlock,
    ocr_from_file,
    ocr_from_url,
)

__version__ = "0.1.0"
__all__ = [
    "OCRHandler",
    "OCRResult",
    "TextBlock",
    "ocr_from_file",
    "ocr_from_url",
]
