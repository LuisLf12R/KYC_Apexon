"""
schema_harmonizer.py
--------------------
Normalizes heterogeneous input DataFrames into the engine's canonical schema.

Flow:
  1. Compute schema fingerprint from (input columns + target type)
  2. Cache lookup via ScriptCacheManager
  3. Cache hit  -> execute cached normalize() script
  4. Cache miss -> call Claude -> cache -> execute
  5. Validate output: if >50% of rows missing any CRITICAL field, REJECT
  6. If accepted, return normalized DataFrame + quality report

Scripts cached under doc_type "schema_normalize_<target_type>".
"""

import hashlib
import json
import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd

from llm_integration.script_cache_manager import ScriptCacheManager
from llm_integration.llm_code_generator import LLMCodeGenerator
from src.canonical_schemas import get_schema, CANONICAL_SCHEMAS

logger = logging.getLogger(__name__)

REJECT_THRESHOLD = 0.50  # Reject if >50% of rows missing a critical field


class HarmonizationRejected(Exception):
    """
    Raised when source data fails critical-field coverage check.
    The exception carries a structured report for the UI to render.
    """
    def __init__(self, report: Dict):
        self.report = report
        msg = report.get("human_readable", "Harmonization rejected")
        super().__init__(msg)


class SchemaHarmonizer:
    SUPPORTED_TARGETS = set(CANONICAL_SCHEMAS.keys())

    def __init__(
        self,
        cache_dir: str = "./scripts_cache",
        anthropic_api_key: Optional[str] = None,
    ):
        self.cache_manager = ScriptCacheManager(cache_dir)
        self.llm_generator = LLMCodeGenerator(api_key=anthropic_api_key)

    def normalize(
        self, df: pd.DataFrame, target_type: str
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Normalize a DataFrame to the canonical schema for target_type.

        Returns (normalized_df, metadata).
        Raises HarmonizationRejected if critical fields fail coverage threshold.
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
                "row_count_in": 0,
                "row_count_out": 0,
                "critical_coverage": {},
                "nice_coverage": {},
            }

        # Defensive column dedup
        if df.columns.duplicated().any():
            dup_cols = df.columns[df.columns.duplicated()].tolist()
            logger.warning(f"Dropping duplicate columns in '{target_type}': {dup_cols}")
            df = df.loc[:, ~df.columns.duplicated()]

        schema = get_schema(target_type)
        input_columns = list(df.columns)
        fingerprint = self._compute_fingerprint(input_columns, target_type)

        # Cache lookup
        cached = self.cache_manager.find_script(
            layout_hash=fingerprint, ocr_text=None, fuzzy_threshold=0.0,
        )

        if cached:
            logger.info(f"Schema cache HIT for '{target_type}' (script {cached['id']})")
            normalized_df = self._execute_normalize_script(cached["id"], df)
            source = "cache"
            script_id = cached["id"]
        else:
            logger.info(f"Schema cache MISS for '{target_type}' — calling LLM")
            script_code = self._generate_normalize_script(
                input_columns=input_columns,
                sample_rows=df.head(5).to_dict(orient="records"),
                schema=schema,
            )
            is_valid, err = self._validate_normalize_script(script_code)
            if not is_valid:
                raise RuntimeError(f"Generated normalize script failed validation: {err}")

            script_id = self.cache_manager.save_script(
                script_code=script_code,
                schema_code="",
                layout_hash=fingerprint,
                fields=schema.all_fields,
                doc_type=f"schema_normalize_{target_type}",
                source="generated",
                confidence_threshold=0.85,
            )
            normalized_df = self._execute_normalize_script(script_id, df)
            source = "generated"

        # Enforce all canonical columns exist
        normalized_df = self._enforce_canonical_columns(normalized_df, schema.all_fields)

        # Coverage analysis
        critical_coverage, nice_coverage = self._compute_coverage(
            normalized_df, schema
        )

        # Decide accept / reject
        failing_critical = {
            f: pct for f, pct in critical_coverage.items()
            if pct < (1.0 - REJECT_THRESHOLD)
        }

        if failing_critical:
            report = self._build_rejection_report(
                target_type=target_type,
                row_count=len(normalized_df),
                failing_critical=failing_critical,
                input_columns=input_columns,
                schema=schema,
                source=source,
                script_id=script_id,
            )
            logger.warning(
                f"Harmonization REJECTED for '{target_type}': "
                f"{list(failing_critical.keys())}"
            )
            raise HarmonizationRejected(report)

        metadata = {
            "source": source,
            "script_id": script_id,
            "row_count_in": len(df),
            "row_count_out": len(normalized_df),
            "critical_coverage": critical_coverage,
            "nice_coverage": nice_coverage,
            "target_type": target_type,
        }
        return normalized_df, metadata

    # -- helpers -------------------------------------------------------------

    def purge_stale_cache(self) -> int:
        """
        Delete all cached schema_normalize_* scripts.
        Used on app startup to force regeneration under the current canonical schema.
        Returns count of scripts purged.
        """
        scripts = self.cache_manager.list_scripts()
        purged = 0
        for s in scripts:
            if s.get("doc_type", "").startswith("schema_normalize_"):
                self.cache_manager.delete_script(s["id"])
                purged += 1
        if purged:
            logger.info(f"Purged {purged} stale schema normalize scripts from cache")
        return purged

    def _compute_fingerprint(self, input_columns, target_type) -> str:
        payload = json.dumps(
            {"columns": sorted(input_columns), "target": target_type},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _generate_normalize_script(self, input_columns, sample_rows, schema) -> str:
        generated = self.llm_generator.generate_schema_normalize_script(
            input_columns=input_columns,
            sample_rows=sample_rows,
            schema=schema,
        )
        return generated.script_code

    def _validate_normalize_script(self, script_code: str) -> Tuple[bool, str]:
        try:
            compile(script_code, "<normalize>", "exec")
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        if "def normalize(" not in script_code:
            return False, "normalize() function not found"
        return True, ""

    def _execute_normalize_script(self, script_id: str, df: pd.DataFrame) -> pd.DataFrame:
        script = self.cache_manager.load_script(script_id)
        namespace = {"pd": pd}
        exec(script["code"], namespace)
        if "normalize" not in namespace:
            raise RuntimeError(f"Cached script {script_id} missing normalize()")
        result = namespace["normalize"](df)
        if not isinstance(result, pd.DataFrame):
            raise RuntimeError(
                f"normalize() returned {type(result).__name__}, expected DataFrame"
            )
        return result

    def _enforce_canonical_columns(self, df: pd.DataFrame, canonical_fields) -> pd.DataFrame:
        for field in canonical_fields:
            if field not in df.columns:
                df[field] = None
        return df

    def _compute_coverage(self, df: pd.DataFrame, schema) -> Tuple[Dict, Dict]:
        """
        For each field, compute fraction of rows where the value is not null/empty.
        Returns (critical_coverage, nice_coverage) as dicts of field -> fraction.
        """
        total = len(df)
        if total == 0:
            return {}, {}

        def coverage(field: str) -> float:
            if field not in df.columns:
                return 0.0
            col = df[field]
            filled = col.notna() & (col.astype(str).str.strip() != "") & (col.astype(str).str.lower() != "none")
            return float(filled.sum()) / total

        crit = {f: coverage(f) for f in schema.critical_fields}
        nice = {f: coverage(f) for f in schema.nice_fields}
        return crit, nice

    def _build_rejection_report(
        self, target_type, row_count, failing_critical, input_columns, schema, source, script_id
    ) -> Dict:
        """
        Build a structured, informative rejection report.
        The UI consumes this to render a detailed error with root-cause guidance.
        """
        lines = []
        lines.append(f"Harmonization rejected for dataset '{target_type}'.")
        lines.append(
            f"Source file has {row_count} rows. "
            f"{len(failing_critical)} critical field(s) fell below "
            f"{int((1.0 - REJECT_THRESHOLD) * 100)}% coverage:"
        )
        lines.append("")
        field_diagnostics = []
        for field, pct in failing_critical.items():
            missing_rows = int(row_count * (1.0 - pct))
            missing_pct = int((1.0 - pct) * 100)
            lines.append(
                f"  • {field}: {missing_rows} of {row_count} rows "
                f"({missing_pct}%) unmappable from source"
            )
            # Hint: which input columns might have contained this data
            likely = self._suggest_source_columns(field, input_columns)
            if likely:
                lines.append(f"    Looked for: {', '.join(likely)} — not found or unmappable")
            field_diagnostics.append({
                "field": field,
                "coverage_pct": round(pct * 100, 1),
                "missing_rows": missing_rows,
                "missing_pct": missing_pct,
                "likely_source_keys": likely,
            })
        lines.append("")
        lines.append("This file cannot be processed by the compliance engine.")
        lines.append(
            "Root cause: the source system did not provide the data required for evaluation. "
            "Enrich the upstream export with these fields and re-upload, or contact the "
            "data owner to investigate why they are missing."
        )

        return {
            "target_type": target_type,
            "row_count": row_count,
            "threshold_pct": int((1.0 - REJECT_THRESHOLD) * 100),
            "failing_fields": field_diagnostics,
            "input_columns_seen": input_columns,
            "critical_fields_required": schema.critical_fields,
            "harmonization_source": source,
            "script_id": script_id,
            "human_readable": "\n".join(lines),
        }

    def _suggest_source_columns(self, canonical_field: str, input_columns: List[str]) -> List[str]:
        """
        Heuristic: return input columns that share tokens with the canonical field.
        Purely informational — helps the user see what the harmonizer attempted.
        """
        field_tokens = canonical_field.lower().replace("_", " ").split()
        candidates = []
        for col in input_columns:
            col_lower = col.lower().replace("_", " ")
            if any(tok in col_lower for tok in field_tokens):
                candidates.append(col)
        return candidates[:5]
