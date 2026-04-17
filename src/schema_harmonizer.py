"""
schema_harmonizer.py
--------------------
Normalizes heterogeneous input DataFrames into the canonical schema defined
by src/data/contracts/contracts.py.

Flow:
  1. Compute schema fingerprint from (input column names + target dataset type)
  2. Cache lookup via ScriptCacheManager
  3. Cache hit  -> execute cached normalize() script
  4. Cache miss -> call Claude to generate normalize(df) -> cache -> execute
  5. Return normalized DataFrame matching the canonical schema

Scripts are cached under doc_type "schema_normalize_<target_type>" (e.g.
"schema_normalize_customers") so that the same input shape for the same
dataset type reuses the cached script.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from llm_integration.script_cache_manager import ScriptCacheManager
from llm_integration.llm_code_generator import LLMCodeGenerator
from src.data.contracts import get_contract

logger = logging.getLogger(__name__)


class SchemaHarmonizer:
    """
    Harmonizes arbitrary-schema DataFrames into the canonical schema.
    Uses ScriptCacheManager for script persistence.
    """

    SUPPORTED_TARGETS = {
        "customers",
        "screenings",
        "id_verifications",
        "documents",
        "transactions",
        "ubo",
    }

    def __init__(
        self,
        cache_dir: str = "./scripts_cache",
        anthropic_api_key: Optional[str] = None,
    ):
        self.cache_manager = ScriptCacheManager(cache_dir)
        self.llm_generator = LLMCodeGenerator(api_key=anthropic_api_key)

    def normalize(
        self,
        df: pd.DataFrame,
        target_type: str,
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Normalize an input DataFrame into the canonical schema for target_type.

        Args:
            df: Input DataFrame with arbitrary schema
            target_type: One of SUPPORTED_TARGETS

        Returns:
            (normalized_df, metadata)
            metadata has keys:
              - source: "cache" or "generated"
              - script_id: cache identifier of the script used
              - input_columns: list of input column names
              - output_columns: list of output column names
              - row_count_in: int
              - row_count_out: int
        """
        if target_type not in self.SUPPORTED_TARGETS:
            raise ValueError(
                f"Unsupported target_type '{target_type}'. "
                f"Must be one of {sorted(self.SUPPORTED_TARGETS)}."
            )

        if df is None or df.empty:
            logger.warning(f"Input DataFrame for '{target_type}' is empty")
            return df, {
                "source": "passthrough",
                "script_id": None,
                "input_columns": [],
                "output_columns": [],
                "row_count_in": 0,
                "row_count_out": 0,
            }

        # Dedupe columns defensively — if input has duplicate column names,
        # keep first occurrence only. This prevents the DataFrame.str AttributeError.
        if df.columns.duplicated().any():
            dup_cols = df.columns[df.columns.duplicated()].tolist()
            logger.warning(f"Dropping duplicate columns in '{target_type}': {dup_cols}")
            df = df.loc[:, ~df.columns.duplicated()]

        input_columns = list(df.columns)
        fingerprint = self._compute_fingerprint(input_columns, target_type)

        contract = get_contract(target_type)
        canonical_fields = sorted(contract.allowed_fields)

        cached = self.cache_manager.find_script(
            layout_hash=fingerprint,
            ocr_text=None,
            fuzzy_threshold=0.0,
        )

        if cached:
            logger.info(
                f"Schema normalize cache HIT for '{target_type}' "
                f"(script {cached['id']})"
            )
            normalized_df = self._execute_normalize_script(cached["id"], df)
            source = "cache"
            script_id = cached["id"]
        else:
            logger.info(
                f"Schema normalize cache MISS for '{target_type}' — "
                f"calling Claude"
            )
            script_code = self._generate_normalize_script(
                input_columns=input_columns,
                sample_rows=df.head(3).to_dict(orient="records"),
                canonical_fields=canonical_fields,
                target_type=target_type,
            )

            # Validate the script compiles and exposes normalize()
            is_valid, err = self._validate_normalize_script(script_code)
            if not is_valid:
                raise RuntimeError(
                    f"Generated normalize script failed validation: {err}"
                )

            script_id = self.cache_manager.save_script(
                script_code=script_code,
                schema_code="",
                layout_hash=fingerprint,
                fields=canonical_fields,
                doc_type=f"schema_normalize_{target_type}",
                source="generated",
                confidence_threshold=0.85,
            )

            normalized_df = self._execute_normalize_script(script_id, df)
            source = "generated"

        # Guarantee all canonical fields exist (fill missing with None)
        normalized_df = self._enforce_canonical_columns(
            normalized_df, canonical_fields
        )

        metadata = {
            "source": source,
            "script_id": script_id,
            "input_columns": input_columns,
            "output_columns": list(normalized_df.columns),
            "row_count_in": len(df),
            "row_count_out": len(normalized_df),
        }
        return normalized_df, metadata

    # -- internal helpers -----------------------------------------------------

    def _compute_fingerprint(
        self, input_columns: List[str], target_type: str
    ) -> str:
        """
        Stable fingerprint = SHA256 of (sorted column names + target type).
        Order-independent, so the same columns in a different order reuse cache.
        """
        payload = json.dumps(
            {"columns": sorted(input_columns), "target": target_type},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _generate_normalize_script(
        self,
        input_columns: List[str],
        sample_rows: List[Dict],
        canonical_fields: List[str],
        target_type: str,
    ) -> str:
        """
        Delegates to LLMCodeGenerator.generate_schema_normalize_script.
        """
        generated = self.llm_generator.generate_schema_normalize_script(
            input_columns=input_columns,
            sample_rows=sample_rows,
            canonical_fields=canonical_fields,
            target_type=target_type,
        )
        return generated.script_code

    def _validate_normalize_script(self, script_code: str) -> Tuple[bool, str]:
        """
        Compile-check the script and confirm it defines normalize(df).
        """
        try:
            compile(script_code, "<normalize>", "exec")
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        if "def normalize(" not in script_code:
            return False, "normalize() function not found in generated code"
        return True, ""

    def _execute_normalize_script(
        self, script_id: str, df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Load and execute the normalize(df) script. Returns the normalized
        DataFrame. Does NOT pass through cache_manager.execute_script because
        that helper is hardcoded to call cleanup(ocr_text).
        """
        script = self.cache_manager.load_script(script_id)
        namespace = {"pd": pd}
        exec(script["code"], namespace)
        if "normalize" not in namespace:
            raise RuntimeError(
                f"Cached script {script_id} does not define normalize()"
            )
        result = namespace["normalize"](df)
        if not isinstance(result, pd.DataFrame):
            raise RuntimeError(
                f"normalize() returned {type(result).__name__}, expected DataFrame"
            )
        return result

    def _enforce_canonical_columns(
        self, df: pd.DataFrame, canonical_fields: List[str]
    ) -> pd.DataFrame:
        """
        Ensure every canonical field exists as a column. Missing fields are
        filled with None. Extra columns not in the canonical schema are kept
        (for audit/debug) but the canonical ones are guaranteed.
        """
        for field in canonical_fields:
            if field not in df.columns:
                df[field] = None
        return df


# Convenience function
def harmonize(
    df: pd.DataFrame,
    target_type: str,
    cache_dir: str = "./scripts_cache",
) -> Tuple[pd.DataFrame, Dict]:
    """Shortcut: one-shot harmonization."""
    harmonizer = SchemaHarmonizer(cache_dir=cache_dir)
    return harmonizer.normalize(df, target_type)
