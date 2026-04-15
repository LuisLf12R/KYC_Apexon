"""
Execution Engine: Orchestrates the complete extraction pipeline
OCR -> Cache lookup -> Script execution -> LLM generation -> Cache store
"""

import os
import sys
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from llm_integration.script_cache_manager import ScriptCacheManager
from llm_integration.llm_code_generator import LLMCodeGenerator

_log = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of extraction pipeline"""
    extracted_data: Dict  # Extracted fields
    source: str  # "cache" or "generated"
    script_id: str  # Which script was used
    ocr_confidence: float  # OCR confidence
    script_confidence: float  # Script generation confidence
    execution_time_seconds: float
    warnings: list


class ExecutionEngine:
    """
    Complete extraction pipeline orchestrator.
    
    Workflow:
    1. Extract text from image with OCR
    2. Check cache for existing script (exact or fuzzy match)
    3. If found: execute cached script (fast!)
    4. If not found: Claude generates new script + cache it
    5. Return extracted data + metadata
    """

    def __init__(
        self,
        cache_dir: str = "./scripts_cache",
        anthropic_api_key: Optional[str] = None
    ):
        """
        Initialize execution engine.
        
        Args:
            cache_dir: Path to script cache directory
            anthropic_api_key: Anthropic API key (uses env var if not provided)
        """
        self.cache_manager = ScriptCacheManager(cache_dir)
        self.llm_generator = LLMCodeGenerator(api_key=anthropic_api_key)

    def extract_from_image(
        self,
        image_path: str,
        doc_type: str,
        fuzzy_match_threshold: float = 0.85
    ) -> ExecutionResult:
        """
        Complete extraction pipeline from image file.
        
        Args:
            image_path: Path to image file
            doc_type: Document type (e.g., "kyc_handwritten")
            fuzzy_match_threshold: Min similarity for fuzzy match (0-1)
            
        Returns:
            ExecutionResult with extracted data and metadata
        """
        import time
        start_time = time.time()

        # Lazy import — keeps OCR dependency out of module-level imports
        # so ExecutionEngine can be imported without Google Vision being set up
        from llm_integration.ocr_handler import ocr_from_file

        # Step 1: OCR extraction
        _log.debug("Step 1/4: OCR extraction")
        ocr_result = ocr_from_file(image_path)
        ocr_text = ocr_result.full_text
        ocr_confidence = ocr_result.confidence

        # Step 2: Cache lookup
        _log.debug("Step 2/4: Cache lookup")
        layout_hash = self.cache_manager.compute_layout_hash(ocr_text)
        cached_script = self.cache_manager.find_script(
            layout_hash=layout_hash,
            ocr_text=ocr_text,
            fuzzy_threshold=fuzzy_match_threshold
        )

        if cached_script:
            # Step 3a: Execute cached script
            _log.debug("Step 3/4: Cache hit — script %s", cached_script['id'])
            extracted_data = self._execute_script(
                cached_script['id'],
                ocr_text
            )

            execution_time = time.time() - start_time

            return ExecutionResult(
                extracted_data=extracted_data,
                source="cache",
                script_id=cached_script['id'],
                ocr_confidence=ocr_confidence,
                script_confidence=cached_script['confidence_threshold'],
                execution_time_seconds=execution_time,
                warnings=ocr_result.warnings
            )

        else:
            # Step 3b: Generate new script with Claude
            _log.debug("Step 3/4: Cache miss — generating with Claude")
            generated_script = self.llm_generator.generate_cleanup_script(
                ocr_text=ocr_text,
                doc_type=doc_type,
                confidence_threshold=ocr_confidence
            )

            # Validate generated script
            is_valid, error = self.llm_generator.validate_generated_script(
                generated_script
            )

            if not is_valid:
                _log.warning("Script validation failed: %s", error)

            # Step 4: Cache the generated script
            _log.debug("Step 4/4: Caching generated script")
            script_id = self.cache_manager.save_script(
                script_code=generated_script.script_code,
                schema_code=generated_script.schema_code,
                layout_hash=layout_hash,
                fields=generated_script.fields,
                doc_type=doc_type,
                source="generated",
                confidence_threshold=generated_script.confidence
            )

            # Execute the newly generated script
            extracted_data = self._execute_script(script_id, ocr_text)

            execution_time = time.time() - start_time

            return ExecutionResult(
                extracted_data=extracted_data,
                source="generated",
                script_id=script_id,
                ocr_confidence=ocr_confidence,
                script_confidence=generated_script.confidence,
                execution_time_seconds=execution_time,
                warnings=ocr_result.warnings + [
                    f"New script generated: {generated_script.explanation}"
                ]
            )

    def extract_from_text(
        self,
        ocr_text: str,
        doc_type: str,
        fuzzy_match_threshold: float = 0.85
    ) -> ExecutionResult:
        """
        Extract fields from OCR text (skip OCR step).
        
        Args:
            ocr_text: Full OCR extracted text
            doc_type: Document type
            fuzzy_match_threshold: Min similarity for fuzzy match
            
        Returns:
            ExecutionResult with extracted data
        """
        import time
        start_time = time.time()

        _log.debug("Step 1/3: Cache lookup")
        layout_hash = self.cache_manager.compute_layout_hash(ocr_text)
        cached_script = self.cache_manager.find_script(
            layout_hash=layout_hash,
            ocr_text=ocr_text,
            fuzzy_threshold=fuzzy_match_threshold
        )

        if cached_script:
            _log.debug("Step 2/3: Cache hit — script %s", cached_script['id'])
            extracted_data = self._execute_script(cached_script['id'], ocr_text)

            execution_time = time.time() - start_time

            return ExecutionResult(
                extracted_data=extracted_data,
                source="cache",
                script_id=cached_script['id'],
                ocr_confidence=1.0,
                script_confidence=cached_script['confidence_threshold'],
                execution_time_seconds=execution_time,
                warnings=[]
            )

        else:
            _log.debug("Step 2/3: Cache miss — generating with Claude")
            generated_script = self.llm_generator.generate_cleanup_script(
                ocr_text=ocr_text,
                doc_type=doc_type
            )

            is_valid, error = self.llm_generator.validate_generated_script(
                generated_script
            )

            if not is_valid:
                _log.warning("Script validation failed: %s", error)

            _log.debug("Step 3/3: Caching generated script")
            script_id = self.cache_manager.save_script(
                script_code=generated_script.script_code,
                schema_code=generated_script.schema_code,
                layout_hash=layout_hash,
                fields=generated_script.fields,
                doc_type=doc_type,
                source="generated",
                confidence_threshold=generated_script.confidence
            )

            extracted_data = self._execute_script(script_id, ocr_text)

            execution_time = time.time() - start_time

            return ExecutionResult(
                extracted_data=extracted_data,
                source="generated",
                script_id=script_id,
                ocr_confidence=1.0,
                script_confidence=generated_script.confidence,
                execution_time_seconds=execution_time,
                warnings=[f"New script generated: {generated_script.explanation}"]
            )

    def transform_structured_data(
        self,
        rows: list,
        doc_type: str,
        target_schema: Dict[str, list],
    ) -> Dict:
        """
        Transform structured input rows into engine-ready tables via the LLM pipeline.

        Same cache-first pattern as extract_from_text():
          1. Fingerprint input schema + target schema
          2. Look up cached transform script
          3. Cache miss → Claude generates def transform(rows) -> dict
          4. Cache → execute → return {table_name: [row_dicts]}

        Args:
            rows: List of input dicts (scenario manifest rows)
            doc_type: Cache key (e.g. "scenario_manifest_to_kyc_tables")
            target_schema: {table_name: [column_names]}

        Returns:
            Dict mapping table name to list of row dicts, or {} on failure
        """
        import time
        import json as _json

        if not rows:
            return {}

        start_time = time.time()

        schema_fingerprint = _json.dumps(
            {"columns": sorted(rows[0].keys()), "target": target_schema},
            sort_keys=True,
        )
        layout_hash = self.cache_manager.compute_layout_hash(schema_fingerprint)

        cached_script = self.cache_manager.find_script(
            layout_hash=layout_hash,
            ocr_text=schema_fingerprint,
            fuzzy_threshold=0.95,
        )

        if cached_script:
            _log.debug("Schema transform: cache hit — script %s", cached_script["id"])
            try:
                result = self.cache_manager.execute_script(
                    cached_script["id"], rows, function_name="transform"
                )
                _log.debug("Schema transform (cached) in %.2fs", time.time() - start_time)
                return result
            except Exception as e:
                _log.warning("Cached transform failed (%s) — regenerating", e)

        _log.debug("Schema transform: cache miss — generating with Claude")
        generated = self.llm_generator.generate_schema_transform_script(
            input_columns=list(rows[0].keys()),
            sample_rows=rows[:3],
            target_schema=target_schema,
            doc_type=doc_type,
        )

        script_id = self.cache_manager.save_script(
            script_code=generated.script_code,
            schema_code="",
            layout_hash=layout_hash,
            fields=list(target_schema.keys()),
            doc_type=doc_type,
            source="generated",
            confidence_threshold=generated.confidence,
        )

        try:
            result = self.cache_manager.execute_script(
                script_id, rows, function_name="transform"
            )
            _log.debug("Schema transform (generated) in %.2fs", time.time() - start_time)
            return result
        except Exception as e:
            _log.error("Transform script execution failed: %s", e)
            return {}

    def _execute_script(self, script_id: str, ocr_text: str) -> Dict:
        """
        Execute a cached script safely.
        
        Args:
            script_id: Script to execute
            ocr_text: OCR text to extract from
            
        Returns:
            Extracted data dict
        """
        try:
            result = self.cache_manager.execute_script(script_id, ocr_text)
            return result
        except Exception as e:
            _log.warning("Script execution failed: %s", e)
            return {"error": str(e)}

    def list_cached_scripts(self) -> list:
        """List all cached scripts"""
        return self.cache_manager.list_scripts()

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return self.cache_manager.get_cache_stats()

    def clear_cache(self) -> bool:
        """Clear all cached scripts"""
        try:
            for script in self.cache_manager.list_scripts():
                self.cache_manager.delete_script(script['id'])
            return True
        except Exception as e:
            _log.error("Cache clear failed: %s", e)
            return False


def extract_from_image(
    image_path: str,
    doc_type: str,
    cache_dir: str = str(Path(__file__).resolve().parent.parent / "scripts_cache")
) -> ExecutionResult:
    """Convenience function for single extraction"""
    engine = ExecutionEngine(cache_dir=cache_dir)
    return engine.extract_from_image(image_path, doc_type)


def extract_from_text(
    ocr_text: str,
    doc_type: str,
    cache_dir: str = str(Path(__file__).resolve().parent.parent / "scripts_cache")
) -> ExecutionResult:
    """Convenience function for text extraction"""
    engine = ExecutionEngine(cache_dir=cache_dir)
    return engine.extract_from_text(ocr_text, doc_type)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python execution_engine.py <image_path> <doc_type>")
        print("Example: python execution_engine.py document.jpg kyc_handwritten")
        sys.exit(1)

    image_path = sys.argv[1]
    doc_type = sys.argv[2]

    print("=" * 70)
    print("Extraction Pipeline")
    print("=" * 70)

    try:
        result = extract_from_image(image_path, doc_type)

        print("\n" + "=" * 70)
        print("Extraction Complete")
        print("=" * 70)
        print(f"Source: {result.source}")
        print(f"Script: {result.script_id}")
        print(f"Execution time: {result.execution_time_seconds:.2f}s")
        print(f"OCR confidence: {result.ocr_confidence:.1%}")
        print(f"Script confidence: {result.script_confidence:.1%}")

        print(f"\nExtracted data:")
        for key, value in result.extracted_data.items():
            print(f"  {key}: {value}")

        if result.warnings:
            print(f"\nWarnings:")
            for warning in result.warnings:
                print(f"  - {warning}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
