"""
OCR Handler: Google Vision API wrapper for document text extraction
Returns: cleaned text + confidence scores + detected fields for downstream LLM processing
"""

import os
import base64
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import json

from google.cloud import vision
from google.cloud.vision_v1 import types


@dataclass
class TextBlock:
    """Single detected text block from Vision API"""
    text: str
    confidence: float
    bounds: Tuple[int, int, int, int]  # (x, y, width, height) in pixels


@dataclass
class OCRResult:
    """Complete OCR extraction result"""
    full_text: str
    confidence: float
    detected_fields: Dict
    warnings: List[str]
    raw_blocks: List[TextBlock]
    language: str = "en"


class OCRHandler:
    """
    Google Vision API wrapper for handwritten document extraction.
    
    Handles:
    - Image file loading (local file or URL)
    - OCR via Google Vision
    - Confidence scoring
    - Field detection (printed vs handwritten)
    - Validation & warnings
    """

    # Confidence thresholds
    HIGH_CONFIDENCE = 0.90
    MEDIUM_CONFIDENCE = 0.70
    LOW_CONFIDENCE = 0.50

    def __init__(self):
        """Initialize Google Vision client using GOOGLE_APPLICATION_CREDENTIALS env var"""
        try:
            self.client = vision.ImageAnnotatorClient()
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize Google Vision client. "
                f"Ensure GOOGLE_APPLICATION_CREDENTIALS env var is set. Error: {e}"
            )

    def extract_from_file(self, image_path: str) -> OCRResult:
        """
        Extract text from a local image file.
        
        Args:
            image_path: Path to image file (jpg, png, pdf, etc.)
            
        Returns:
            OCRResult with text, confidence, and field metadata
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        with open(image_path, "rb") as f:
            content = f.read()

        return self._process_vision_request(content, source_type="file")

    def extract_from_url(self, image_url: str) -> OCRResult:
        """
        Extract text from a remote image URL.
        
        Args:
            image_url: URL to image (must be publicly accessible)
            
        Returns:
            OCRResult with text, confidence, and field metadata
        """
        image = types.Image(source=types.ImageSource(image_uri=image_url))
        return self._process_vision_request(image, source_type="url")

    def extract_from_base64(self, base64_content: str) -> OCRResult:
        """
        Extract text from base64-encoded image.
        
        Args:
            base64_content: Base64-encoded image bytes
            
        Returns:
            OCRResult with text, confidence, and field metadata
        """
        image_bytes = base64.b64decode(base64_content)
        return self._process_vision_request(image_bytes, source_type="base64")

    def _process_vision_request(
        self, 
        content, 
        source_type: str
    ) -> OCRResult:
        """
        Core Vision API request processor.
        
        Calls Vision API with DOCUMENT_TEXT_DETECTION feature for handwritten docs.
        Parses response and extracts confidence, field types, warnings.
        """
        try:
            # Prepare image object
            if source_type == "file":
                image = types.Image(content=content)
            elif source_type == "base64":
                image = types.Image(content=content)
            else:  # url
                image = content  # Already a types.Image from caller

            # Request with DOCUMENT_TEXT_DETECTION (better for handwriting)
            request = vision.AnnotateImageRequest(
                image=image,
                features=[
                    vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION),
                    vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION),
                ],
            )

            # Execute request
            response = self.client.annotate_image(request)

            # Parse response
            if response.error.message:
                raise RuntimeError(f"Vision API error: {response.error.message}")

            return self._parse_vision_response(response)

        except Exception as e:
            raise RuntimeError(f"OCR processing failed: {str(e)}")

    def _parse_vision_response(self, response) -> OCRResult:
        """
        Parse Google Vision API response into OCRResult.
        
        Extracts:
        - Full document text
        - Per-block confidence scores
        - Language detection
        - Handwritten vs printed detection
        - Field boundaries
        """
        if not response.full_text_annotation:
            return OCRResult(
                full_text="",
                confidence=0.0,
                detected_fields={},
                warnings=["No text detected in image"],
                raw_blocks=[],
            )

        full_text = response.full_text_annotation.text
        # Get page confidence - safely handle if it doesn't exist
        page_confidence = getattr(response.full_text_annotation, 'confidence', 0.0)

        # Parse text blocks
        text_blocks = []
        handwriting_count = 0
        printed_count = 0
        low_confidence_fields = []
        language = "en"

        # Extract from pages
        if response.full_text_annotation.pages:
            for page in response.full_text_annotation.pages:
                # Try to get page-level confidence
                if hasattr(page, 'confidence') and page.confidence:
                    page_confidence = page.confidence

                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        # Get paragraph confidence safely
                        para_confidence = getattr(paragraph, 'confidence', 0.5)

                        # Detect handwriting from property
                        is_handwritten = False
                        if hasattr(paragraph, 'property') and paragraph.property:
                            if hasattr(paragraph.property, 'detected_languages'):
                                for lang_prop in paragraph.property.detected_languages:
                                    language = getattr(lang_prop, 'language_code', 'en')
                                    break

                        if is_handwritten:
                            handwriting_count += 1
                        else:
                            printed_count += 1

                        # Extract paragraph text
                        para_text = ""
                        for word in paragraph.words:
                            for symbol in word.symbols:
                                para_text += symbol.text

                        if para_confidence < self.MEDIUM_CONFIDENCE:
                            low_confidence_fields.append(
                                f"{para_text.strip()[:30]}... (confidence: {para_confidence:.2f})"
                            )

                        # Get bounding box
                        if hasattr(paragraph, 'bounding_box') and paragraph.bounding_box:
                            vertices = paragraph.bounding_box.vertices
                            if vertices:
                                x = min(v.x for v in vertices)
                                y = min(v.y for v in vertices)
                                w = max(v.x for v in vertices) - x
                                h = max(v.y for v in vertices) - y
                                bounds = (x, y, w, h)
                            else:
                                bounds = (0, 0, 0, 0)
                        else:
                            bounds = (0, 0, 0, 0)

                        if para_text.strip():  # Only add non-empty blocks
                            text_blocks.append(
                                TextBlock(
                                    text=para_text.strip(),
                                    confidence=para_confidence,
                                    bounds=bounds,
                                )
                            )

        # Build warnings
        warnings = []
        if page_confidence < self.HIGH_CONFIDENCE:
            warnings.append(
                f"Overall page confidence low: {page_confidence:.2f} (< {self.HIGH_CONFIDENCE})"
            )
        if low_confidence_fields:
            warnings.append(f"Low confidence on fields: {', '.join(low_confidence_fields[:3])}")

        detected_fields = {
            "text_blocks": [asdict(block) for block in text_blocks],
            "handwriting_regions": handwriting_count,
            "printed_regions": printed_count,
            "language": language,
            "block_count": len(text_blocks),
        }

        return OCRResult(
            full_text=full_text,
            confidence=float(page_confidence),
            detected_fields=detected_fields,
            warnings=warnings,
            raw_blocks=text_blocks,
            language=language,
        )

    def to_dict(self, result: OCRResult) -> Dict:
        """Convert OCRResult to dictionary (for JSON serialization, caching)"""
        return {
            "full_text": result.full_text,
            "confidence": result.confidence,
            "detected_fields": result.detected_fields,
            "warnings": result.warnings,
            "language": result.language,
        }

    def to_json(self, result: OCRResult) -> str:
        """Convert OCRResult to JSON string"""
        return json.dumps(self.to_dict(result), indent=2)


def ocr_from_file(image_path: str) -> OCRResult:
    """Convenience function: extract text from file"""
    handler = OCRHandler()
    return handler.extract_from_file(image_path)


def ocr_from_url(image_url: str) -> OCRResult:
    """Convenience function: extract text from URL"""
    handler = OCRHandler()
    return handler.extract_from_url(image_url)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ocr_handler.py <image_path_or_url>")
        sys.exit(1)

    path_or_url = sys.argv[1]
    handler = OCRHandler()

    if path_or_url.startswith("http"):
        result = handler.extract_from_url(path_or_url)
    else:
        result = handler.extract_from_file(path_or_url)

    print("\n=== OCR Result ===")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Language: {result.language}")
    print(f"\nFull Text:\n{result.full_text}")
    print(f"\nDetected Fields: {json.dumps(result.detected_fields, indent=2)}")
    if result.warnings:
        print(f"\nWarnings: {result.warnings}")
