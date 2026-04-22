"""Backfill reviewed_by on all changelog entries in the live ruleset."""
import json
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rules.schema.ruleset import RulesetManifest

RULESET_PATH = Path("rules/kyc_rules_v2.0.json")
REVIEWER = "NYU RegTech Team"


def main():
    raw = json.loads(RULESET_PATH.read_text())

    changed = 0
    for entry in raw.get("changelog", []):
        if entry.get("reviewed_by") is None:
            entry["reviewed_by"] = REVIEWER
            changed += 1

    # Schema round-trip — will raise if anything is wrong
    validated = RulesetManifest.model_validate(raw)
    out = validated.model_dump(mode="json")

    RULESET_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Backfilled {changed} changelog entries with reviewed_by='{REVIEWER}'")

    # Verify no nulls remain
    reloaded = json.loads(RULESET_PATH.read_text())
    nulls = [e for e in reloaded.get("changelog", []) if e.get("reviewed_by") is None]
    assert len(nulls) == 0, f"Still have {len(nulls)} null reviewed_by entries!"
    print("Verification passed — zero null reviewed_by entries.")


if __name__ == "__main__":
    main()
