import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from benchmarks.config_loader import (
    load_constraint_catalog,
    load_generator_matrix,
    load_scenario_archetypes,
)


OUTPUT_DIR = Path("benchmarks") / "output"
OUTPUT_FILE = OUTPUT_DIR / "scenario_manifest.jsonl"


def _default_run_id() -> str:
    return f"demo_run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _priority_weight(priority: str) -> int:
    p = (priority or "").upper()
    if p == "HIGH":
        return 3
    if p == "MEDIUM":
        return 2
    return 1


def _build_weighted_archetypes(archetypes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    weighted: List[Dict[str, Any]] = []
    for archetype in archetypes:
        weighted.extend([archetype] * _priority_weight(archetype.get("demo_priority", "LOW")))
    return weighted


def _build_scenario(archetype: Dict[str, Any], scenario_number: int, run_id: str) -> Dict[str, Any]:
    defaults = archetype.get("default_states", {})
    scenario = {
        "scenario_id": f"SCENARIO_{scenario_number:04d}",
        "run_id": run_id,
        "archetype_id": archetype.get("archetype_id"),
        "archetype_name": archetype.get("archetype_name"),
        "customer_type": archetype.get("customer_type"),
        "risk_tier": archetype.get("risk_tier"),
        "aml_state": defaults.get("aml_state"),
        "identity_state": defaults.get("identity_state"),
        "poa_state": defaults.get("poa_state"),
        "ubo_state": defaults.get("ubo_state"),
        "activity_state": defaults.get("activity_state"),
        "data_quality_state": defaults.get("data_quality_state"),
        "expected_final_decision": archetype.get("expected_final_decision"),
        "is_remediable_case": bool(archetype.get("is_remediable_case", False)),
        "coverage_tags": archetype.get("coverage_tags", []),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if archetype.get("expected_post_remediation_decision") is not None:
        scenario["expected_post_remediation_decision"] = archetype.get("expected_post_remediation_decision")
    return scenario


def _matches_if_clause(scenario: Dict[str, Any], if_clause: Dict[str, Any]) -> bool:
    for field, expected in if_clause.items():
        if scenario.get(field) != expected:
            return False
    return True


def _apply_constraints(scenario: Dict[str, Any], constraints: List[Dict[str, Any]]) -> Dict[str, Any]:
    updated = dict(scenario)
    for constraint in constraints:
        if_clause = constraint.get("if", {})
        then_clause = constraint.get("then", {})
        if not isinstance(if_clause, dict) or not isinstance(then_clause, dict):
            continue
        if _matches_if_clause(updated, if_clause):
            updated.update(then_clause)
    return updated


def generate_demo_portfolio(size: int, run_id: str | None = None) -> str:
    """
    Generate a demo portfolio and return absolute path to scenario_manifest.jsonl.
    """
    run_id = run_id or _default_run_id()
    out_file = OUTPUT_FILE
    _ = load_generator_matrix()  # loaded for config consistency in v1
    constraints_cfg = load_constraint_catalog()
    archetypes_cfg = load_scenario_archetypes()

    constraints = constraints_cfg.get("constraints", [])
    archetypes = archetypes_cfg.get("archetypes", [])
    if not archetypes:
        raise ValueError("No archetypes found in benchmarks/config/kyc_scenario_archetypes.json")

    print(f"Loaded {len(archetypes)} archetypes.")

    weighted = _build_weighted_archetypes(archetypes)
    scenarios: List[Dict[str, Any]] = []
    for i in range(1, size + 1):
        selected = random.choice(weighted)
        scenario = _build_scenario(selected, i, run_id)
        scenario = _apply_constraints(scenario, constraints)
        scenarios.append(scenario)

    # For validation convenience in v1: ensure at least one BLOCKED sample if S021 exists.
    has_s021 = any(c.get("constraint_id") == "S021" for c in constraints)
    if has_s021 and scenarios and not any(s.get("aml_state") == "BLOCKED" for s in scenarios):
        scenarios[0]["aml_state"] = "BLOCKED"
        scenarios[0] = _apply_constraints(scenarios[0], constraints)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        for scenario in scenarios:
            f.write(json.dumps(scenario) + "\n")

    print(f"Wrote {len(scenarios)} scenarios to {out_file}")
    return str(out_file.resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo KYC scenario portfolio manifest.")
    parser.add_argument("--size", type=int, default=10, help="Number of scenarios to generate.")
    parser.add_argument("--run-id", type=str, default=None, help="Optional run identifier.")
    args = parser.parse_args()

    generate_demo_portfolio(size=args.size, run_id=args.run_id)


if __name__ == "__main__":
    main()
