#!/usr/bin/env python3
"""Diagnose whether OCR pipeline v1 or v2 is currently active."""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent
LLM_DIR = ROOT / "llm_integration"


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _extract_imports(file_path: Path) -> List[str]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)
    return sorted(set(imports))


def _file_report() -> List[Tuple[str, int, str]]:
    rows: List[Tuple[str, int, str]] = []
    for file_path in sorted(LLM_DIR.glob("*.py")):
        imports = _extract_imports(file_path)
        imports_preview = ", ".join(imports[:8])
        if len(imports) > 8:
            imports_preview += ", ..."
        rows.append((file_path.name, file_path.stat().st_size, imports_preview))
    return rows


def _classify_engine_source(module_text: str) -> str:
    has_v1_markers = "self.llm_generator" in module_text or "ScriptCacheManager" in module_text
    has_v2_markers = "self.ocr_extractor" in module_text and "ocr_extractor_v2" in module_text
    if has_v2_markers and not has_v1_markers:
        return "v2"
    if has_v1_markers and not has_v2_markers:
        return "v1"
    if has_v1_markers and has_v2_markers:
        return "mixed"
    return "unknown"


def main() -> int:
    print("=" * 78)
    print("OCR Pipeline Version Diagnosis")
    print("=" * 78)
    print(f"Timestamp: {ts()}")
    print(f"Project root: {ROOT}")
    print(f"Python: {sys.version.split()[0]}")

    if not LLM_DIR.exists():
        print(f"✗ Missing llm_integration directory at: {LLM_DIR}")
        return 1

    print("\n[1] File inventory (.py, size, imports)")
    for name, size, imports_preview in _file_report():
        print(f" - {name:<35} {size:>8} bytes | imports: {imports_preview}")

    issues: List[str] = []

    print("\n[2] Import availability")
    mod_engine = None
    for mod_name in ["llm_integration.execution_engine", "llm_integration.execution_engine_v2", "llm_integration.llm_code_generator", "llm_integration.ocr_extractor_v2"]:
        try:
            module = importlib.import_module(mod_name)
            print(f" ✓ import {mod_name} -> {getattr(module, '__file__', 'unknown')} ")
            if mod_name == "llm_integration.execution_engine":
                mod_engine = module
        except Exception as exc:
            print(f" ✗ import {mod_name} failed: {exc}")
            if mod_name in {"llm_integration.execution_engine", "llm_integration.ocr_extractor_v2"}:
                issues.append(f"Critical import failed: {mod_name} -> {exc}")

    print("\n[3] execution_engine implementation inspection")
    active_version = "unknown"
    engine_path = LLM_DIR / "execution_engine.py"
    if engine_path.exists():
        content = engine_path.read_text(encoding="utf-8", errors="replace")
        active_version = _classify_engine_source(content)
        print(f" - execution_engine.py markers indicate: {active_version}")
        print(f" - contains self.llm_generator: {'self.llm_generator' in content}")
        print(f" - contains self.cache_manager: {'self.cache_manager' in content}")
        print(f" - contains self.ocr_extractor: {'self.ocr_extractor' in content}")
    else:
        print(" ✗ execution_engine.py is missing")
        issues.append("execution_engine.py is missing")

    if mod_engine is not None:
        EngineCls = getattr(mod_engine, "ExecutionEngine", None)
        if EngineCls is None:
            print(" ✗ ExecutionEngine class missing")
            issues.append("ExecutionEngine class missing in llm_integration.execution_engine")
        else:
            print(f" - ExecutionEngine class found: {EngineCls}")
            try:
                init_sig = inspect.signature(EngineCls.__init__)
                print(f" - __init__ signature: {init_sig}")
            except Exception as exc:
                print(f" ⚠ unable to inspect __init__: {exc}")
            for method_name in ["extract_from_image", "extract_from_text"]:
                method = getattr(EngineCls, method_name, None)
                if method is None:
                    print(f" ✗ missing method: {method_name}")
                    issues.append(f"ExecutionEngine missing method: {method_name}")
                else:
                    print(f" - {method_name} signature: {inspect.signature(method)}")

            print("\n[4] Runtime behavior check")
            try:
                engine = EngineCls()
                print(" ✓ ExecutionEngine() instantiated")
                print(f" - hasattr(engine, 'ocr_extractor'): {hasattr(engine, 'ocr_extractor')}")
                print(f" - hasattr(engine, 'cache_manager'): {hasattr(engine, 'cache_manager')}")
                print(f" - hasattr(engine, 'llm_generator'): {hasattr(engine, 'llm_generator')}")
            except Exception as exc:
                print(f" ✗ ExecutionEngine instantiation failed: {exc}")
                issues.append(f"ExecutionEngine() failed: {exc}")
                engine = None

            if engine is not None:
                try:
                    result = engine.extract_from_image("/tmp/nonexistent_ocr_image.png", doc_type_hint="student_id")
                    print(" ✓ extract_from_image() callable with doc_type_hint")
                    print(f" - result type: {type(result).__name__}")
                except TypeError as exc:
                    print(f" ⚠ extract_from_image signature mismatch (likely v1): {exc}")
                except Exception as exc:
                    print(f" ⚠ extract_from_image raised runtime error (handled): {exc}")

    print("\n[5] Diagnosis summary")
    if active_version == "v1":
        print("RESULT: Currently using v1 (legacy cache/code-generation pipeline).")
        issues.append("Active default engine appears to be v1.")
    elif active_version == "v2":
        print("RESULT: Currently using v2 (structured JSON extractor).")
    elif active_version == "mixed":
        print("RESULT: Mixed markers found; migration is inconsistent.")
        issues.append("execution_engine.py contains mixed v1/v2 markers.")
    else:
        print("RESULT: Could not conclusively detect version.")
        issues.append("Unable to classify active engine version.")

    if issues:
        print("\nIssues found:")
        for item in issues:
            print(f" - {item}")
    else:
        print("\nNo blocking issues detected.")

    print("\nRecommended actions:")
    if active_version == "v1" or active_version == "mixed":
        print(" 1) Run: python fix_migration.py")
        print(" 2) Restart all Python/Streamlit processes")
        print(" 3) Run: python validate_ocr_fix.py")
    else:
        print(" 1) Run: python validate_ocr_fix.py")
        print(" 2) Run end-to-end tests with real images")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
