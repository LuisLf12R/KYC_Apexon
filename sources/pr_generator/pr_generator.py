"""
PR generator for ruleset overlay changes.

Flow
----
1. load_staged_overlays()  — read all rules/staging/*.json (skip PR_DRAFT.md)
2. load_live_ruleset()     — read kyc_rules_v2.0.json as raw dict
3. diff_overlays()         — classify each staged overlay as new|modified|unchanged
4. run_regression_gate()   — run pytest, capture pass/fail counts
5. emit_pr_description()   — write rules/staging/PR_DRAFT.md

The generator never writes to kyc_rules_v2.0.json.
Merge is performed manually by the human reviewer after approving the PR.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rules.schema import JurisdictionOverlay

_STAGING_DIR = Path(__file__).parent.parent.parent / "rules" / "staging"
_LIVE_RULESET = Path(__file__).parent.parent.parent / "rules" / "kyc_rules_v2.0.json"
_PR_DRAFT = _STAGING_DIR / "PR_DRAFT.md"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_staged_overlays() -> List[JurisdictionOverlay]:
    """Load and validate all *.json files in rules/staging/ (excluding PR_DRAFT.md)."""
    if not _STAGING_DIR.exists():
        return []
    overlays = []
    for path in sorted(_STAGING_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        overlays.append(JurisdictionOverlay.model_validate(raw))
    return overlays


def load_live_ruleset() -> Dict[str, Any]:
    """Load kyc_rules_v2.0.json as a raw dict."""
    return json.loads(_LIVE_RULESET.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------

def diff_overlays(
    staged: List[JurisdictionOverlay],
    live_ruleset: Dict[str, Any],
) -> Dict[str, List[JurisdictionOverlay]]:
    """Classify staged overlays as new, modified, or unchanged vs live ruleset.

    Returns dict with keys: 'new', 'modified', 'unchanged'.
    """
    live_jurisdictions = live_ruleset.get("jurisdictions", {})
    result: Dict[str, List[JurisdictionOverlay]] = {
        "new": [],
        "modified": [],
        "unchanged": [],
    }
    for overlay in staged:
        code = overlay.jurisdiction_code
        if code not in live_jurisdictions:
            result["new"].append(overlay)
        else:
            live_overlay = live_jurisdictions[code]
            staged_dict = overlay.model_dump(mode="json")
            if staged_dict == live_overlay:
                result["unchanged"].append(overlay)
            else:
                result["modified"].append(overlay)
    return result


def summarise_dimension_overrides(overlay: JurisdictionOverlay) -> List[str]:
    """Return human-readable lines describing the dimension_overrides."""
    lines = []
    for dim, params in overlay.dimension_overrides.items():
        for field, value in params.items():
            lines.append(f"  - `{dim}.{field}` = `{value}`")
    if not lines:
        lines.append("  - No dimension overrides (baseline params apply)")
    return lines


# ---------------------------------------------------------------------------
# Regression gate
# ---------------------------------------------------------------------------

def run_regression_gate(
    test_path: str = "tests/",
    _subprocess_run=None,
) -> Tuple[bool, int, int, str]:
    """Run pytest and return (passed, n_passed, n_failed, summary_line).

    _subprocess_run is an injection point for testing.
    """
    run_fn = _subprocess_run or subprocess.run
    result = run_fn(
        [sys.executable, "-m", "pytest", test_path, "-v", "--tb=no", "-q"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": "."},
    )
    output = result.stdout + result.stderr

    # Parse summary line e.g. "111 passed, 2 warnings in 3.10s"
    n_passed = 0
    n_failed = 0
    summary_line = "unknown"
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            summary_line = line.strip()
            # Extract counts
            import re
            m_passed = re.search(r"(\d+) passed", line)
            m_failed = re.search(r"(\d+) failed", line)
            m_error = re.search(r"(\d+) error", line)
            if m_passed:
                n_passed = int(m_passed.group(1))
            if m_failed:
                n_failed = int(m_failed.group(1))
            if m_error:
                n_failed += int(m_error.group(1))
            break

    gate_passed = result.returncode == 0
    return gate_passed, n_passed, n_failed, summary_line


# ---------------------------------------------------------------------------
# PR description emitter
# ---------------------------------------------------------------------------

def emit_pr_description(
    diff: Dict[str, List[JurisdictionOverlay]],
    gate_passed: bool,
    n_passed: int,
    n_failed: int,
    summary_line: str,
    staged_overlays: List[JurisdictionOverlay],
) -> str:
    """Build and return the markdown PR description string."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    gate_badge = "✅ PASSED" if gate_passed else "❌ FAILED"
    gate_emoji = "✅" if gate_passed else "❌"

    new_overlays = diff["new"]
    modified_overlays = diff["modified"]
    unchanged_overlays = diff["unchanged"]

    lines: List[str] = [
        "# KYC Ruleset — Automated Overlay PR",
        "",
        f"**Generated:** {now}  ",
        f"**Regression gate:** {gate_badge} ({summary_line})  ",
        f"**Staged overlays:** {len(staged_overlays)} jurisdiction(s)",
        "",
    ]

    if not gate_passed:
        lines += [
            "---",
            "",
            "## ⛔ Regression Gate Failed",
            "",
            f"The regression suite reported {n_failed} failure(s). "
            "This PR must NOT be merged until all tests pass.",
            "",
            "Run `PYTHONPATH=. pytest tests/ -v` locally to diagnose.",
            "",
        ]

    # --- New jurisdictions ---
    if new_overlays:
        lines += [
            "---",
            "",
            f"## 🆕 New Jurisdictions ({len(new_overlays)})",
            "",
        ]
        for overlay in new_overlays:
            lines += [
                f"### {overlay.jurisdiction_code}",
                f"**Regulators:** {', '.join(overlay.regulators)}",
                "",
                "**Dimension overrides:**",
            ]
            lines += summarise_dimension_overrides(overlay)
            hr_count = len(overlay.additional_hard_reject_rules)
            rv_count = len(overlay.additional_review_rules)
            lines += [
                "",
                f"**Additional hard-reject rules:** {hr_count}  ",
                f"**Additional review rules:** {rv_count}",
                "",
            ]

    # --- Modified jurisdictions ---
    if modified_overlays:
        lines += [
            "---",
            "",
            f"## ✏️ Modified Jurisdictions ({len(modified_overlays)})",
            "",
        ]
        for overlay in modified_overlays:
            lines += [
                f"### {overlay.jurisdiction_code}",
                f"**Regulators:** {', '.join(overlay.regulators)}",
                "",
                "**Staged dimension overrides:**",
            ]
            lines += summarise_dimension_overrides(overlay)
            lines.append("")

    # --- Unchanged ---
    if unchanged_overlays:
        codes = ", ".join(o.jurisdiction_code for o in unchanged_overlays)
        lines += [
            "---",
            "",
            f"## ⏭️ Unchanged ({len(unchanged_overlays)}): {codes}",
            "",
            "These staged overlays are identical to the live ruleset. "
            "No action required — safe to ignore or remove from staging.",
            "",
        ]

    # --- Merge instructions ---
    lines += [
        "---",
        "",
        "## Merge Instructions",
        "",
        "1. Review each overlay above against the source regulatory text.",
        "2. Confirm regression gate shows ✅ PASSED.",
        "3. Merge staged overlays into `rules/kyc_rules_v2.0.json` "
           "under the `jurisdictions` key.",
        "4. Bump ruleset `version` field and add a `changelog` entry.",
        "5. Tag the commit: `git tag kyc-rules-vX.Y.Z`.",
        "6. Sign off as named reviewer in the changelog entry.",
        "",
        "> **Non-negotiable:** No merge without named human reviewer sign-off. "
          "See architectural decision §8.6.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def generate_pr(
    output_path: Optional[Path] = None,
    _subprocess_run=None,
) -> Path:
    """Full PR generation pipeline. Returns path to PR_DRAFT.md.

    output_path overrides the default rules/staging/PR_DRAFT.md (for testing).
    """
    out = output_path or _PR_DRAFT

    staged = load_staged_overlays()
    live = load_live_ruleset()
    diff = diff_overlays(staged, live)
    gate_passed, n_passed, n_failed, summary_line = run_regression_gate(
        _subprocess_run=_subprocess_run,
    )
    md = emit_pr_description(
        diff=diff,
        gate_passed=gate_passed,
        n_passed=n_passed,
        n_failed=n_failed,
        summary_line=summary_line,
        staged_overlays=staged,
    )

    _STAGING_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return out
