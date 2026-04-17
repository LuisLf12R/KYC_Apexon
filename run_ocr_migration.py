#!/usr/bin/env python3
"""Master script to diagnose, fix, and validate OCR migration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_step(description: str, script_name: str) -> int:
    print("\n" + "=" * 78)
    print(description)
    print("=" * 78)
    cmd = [sys.executable, str(ROOT / script_name)]
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"\n⚠️ Script failed: {script_name}")
    return result.returncode


def main() -> int:
    steps = [
        ("Diagnosing OCR version...", "diagnose_ocr_version.py"),
        ("Fixing migration...", "fix_migration.py"),
        ("Validating fix...", "validate_ocr_fix.py"),
    ]

    for description, script in steps:
        code = run_step(description, script)
        if code != 0:
            print("Stopping migration due to failure.")
            return code

    print("\n" + "=" * 78)
    print("✓ OCR Migration Complete!")
    print("=" * 78)
    print(
        "\nNext steps:\n"
        "1. Restart your Streamlit app or Python process\n"
        "2. Test student ID extraction with a real image\n"
        "3. Verify no more 'document_type' errors\n\n"
        "Windows restart command (if needed):\n"
        "  taskkill /F /IM python.exe\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
