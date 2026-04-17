"""Extract PyArrow/Arrow conversion errors from Railway log export text files.

Usage:
    python scripts/extract_pyarrow_errors.py /path/to/railway.log
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERN = re.compile(
    r"(Arrow(?:Type|Invalid)Error|PyArrow|Expected bytes, got a 'bool' object|Conversion failed for column)",
    re.IGNORECASE,
)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/extract_pyarrow_errors.py /path/to/railway.log")
        return 2

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Log file not found: {path}")
        return 2

    lines = path.read_text(errors="replace").splitlines()
    hits = [idx for idx, line in enumerate(lines) if PATTERN.search(line)]

    if not hits:
        print("No PyArrow-related errors found.")
        return 0

    print(f"Found {len(hits)} PyArrow-related log lines in {path}:")
    for idx in hits:
        start = max(0, idx - 2)
        end = min(len(lines), idx + 3)
        print("\n---")
        for i in range(start, end):
            pointer = ">" if i == idx else " "
            print(f"{pointer} {i+1:06d}: {lines[i]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
