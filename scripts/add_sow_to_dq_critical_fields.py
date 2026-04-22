"""Add sow_declared to data_quality critical_fields in the live ruleset."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rules.schema.ruleset import RulesetManifest

RULESET_PATH = Path("rules/kyc_rules_v2.0.json")
FIELD_TO_ADD = "sow_declared"


def main():
    raw = json.loads(RULESET_PATH.read_text())

    dq = raw.get("dimension_parameters", {}).get("data_quality", {})
    critical = dq.get("critical_fields", [])

    if FIELD_TO_ADD in critical:
        print(f"'{FIELD_TO_ADD}' already in critical_fields — nothing to do.")
        return

    critical.append(FIELD_TO_ADD)
    dq["critical_fields"] = critical
    raw["dimension_parameters"]["data_quality"] = dq

    # Schema round-trip
    validated = RulesetManifest.model_validate(raw)
    out = validated.model_dump(mode="json")

    RULESET_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Added '{FIELD_TO_ADD}' to data_quality critical_fields.")

    # Verify
    reloaded = json.loads(RULESET_PATH.read_text())
    cf = reloaded["dimension_parameters"]["data_quality"]["critical_fields"]
    assert FIELD_TO_ADD in cf, f"'{FIELD_TO_ADD}' not found after write!"
    print(f"Verification passed. critical_fields now: {cf}")


if __name__ == "__main__":
    main()
