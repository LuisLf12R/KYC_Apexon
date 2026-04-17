#!/usr/bin/env python3
"""Promote OCR pipeline v2 to default and archive v1 files."""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent
LLM_DIR = ROOT / "llm_integration"


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def safe_rename(src: Path, dst: Path) -> Tuple[bool, str]:
    if not src.exists():
        return False, f"⚠️ Missing source: {src.name}"
    if dst.exists():
        return False, f"⚠️ Destination exists, skipped: {dst.name}"
    try:
        os.rename(src, dst)
        return True, f"✓ Renamed: {src.name} → {dst.name}"
    except Exception as exc:
        return False, f"✗ Rename failed ({src.name} → {dst.name}): {exc}"


def clear_python_cache(root: Path) -> Tuple[int, int, List[str]]:
    pycache_deleted = 0
    pyc_deleted = 0
    errors: List[str] = []

    for pycache_dir in root.rglob("__pycache__"):
        if pycache_dir.is_dir():
            try:
                shutil.rmtree(pycache_dir)
                pycache_deleted += 1
            except Exception as exc:
                errors.append(f"Failed removing {pycache_dir}: {exc}")

    for pyc_file in root.rglob("*.pyc"):
        if pyc_file.exists():
            try:
                pyc_file.unlink()
                pyc_deleted += 1
            except Exception as exc:
                errors.append(f"Failed removing {pyc_file}: {exc}")

    return pycache_deleted, pyc_deleted, errors


def line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def main() -> int:
    print("Migration Fix Report")
    print("=" * 78)
    print(f"Timestamp: {ts()}")
    print(f"Root: {ROOT}")

    if not LLM_DIR.exists():
        print(f"✗ Missing directory: {LLM_DIR}")
        return 1

    steps: List[str] = []

    # Backup v1 files.
    ok, msg = safe_rename(
        LLM_DIR / "execution_engine.py",
        LLM_DIR / "execution_engine_v1_BACKUP.py",
    )
    steps.append(msg)

    ok2, msg2 = safe_rename(
        LLM_DIR / "llm_code_generator.py",
        LLM_DIR / "llm_code_generator_v1_BACKUP.py",
    )
    steps.append(msg2)

    # Promote v2 file to default path.
    ok3, msg3 = safe_rename(
        LLM_DIR / "execution_engine_v2.py",
        LLM_DIR / "execution_engine.py",
    )
    steps.append(msg3)

    pycache_count, pyc_count, cache_errors = clear_python_cache(ROOT)
    steps.append(f"✓ Cleared Python cache: {pycache_count} __pycache__ dirs, {pyc_count} .pyc files")

    print()
    for step in steps:
        print(step)

    if cache_errors:
        print("\nCache cleanup warnings:")
        for err in cache_errors:
            print(f" - {err}")

    print("\nNew file structure (llm_integration):")
    for fname in [
        "execution_engine.py",
        "ocr_extractor_v2.py",
        "ocr_handler.py",
        "script_cache_manager.py",
        "execution_engine_v1_BACKUP.py",
        "llm_code_generator_v1_BACKUP.py",
    ]:
        path = LLM_DIR / fname
        marker = "(missing)"
        if path.exists():
            marker = f"({line_count(path)} lines)"
        print(f"  - {fname} {marker}")

    print("\nStatus:")
    if (LLM_DIR / "execution_engine.py").exists() and (LLM_DIR / "execution_engine_v1_BACKUP.py").exists():
        print("✓ Migration step complete. Restart your app/process and run validation.")
    else:
        print("⚠️ Migration partially complete. Review messages above before continuing.")

    print("\nNext commands:")
    print("  python validate_ocr_fix.py")
    print("  # Restart app/processes if needed")
    print("  # taskkill /F /IM python.exe   (Windows)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
