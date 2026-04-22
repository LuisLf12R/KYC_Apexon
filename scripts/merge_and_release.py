"""Merge CAN/UAE/IND staged overlays and cut first production release."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sources.merger import merge_staged_overlay
from sources.release import create_release

RULESET_PATH = Path("rules/kyc_rules_v2.0.json")
REVIEWER = "NYU RegTech Team"
JURISDICTIONS = ["CAN", "UAE", "IND"]


def main():
    raw_before = json.loads(RULESET_PATH.read_text())
    prev_version = raw_before.get("version")

    # Merge each staged overlay
    for code in JURISDICTIONS:
        print(f"\n--- Merging {code} ---")
        result = merge_staged_overlay(code, reviewed_by=REVIEWER)
        print(f"{code} merge result: {result}")

    # Cut release
    print("\n--- Creating release ---")
    release_result = create_release("minor", reviewed_by=REVIEWER)
    print(f"Release result: {release_result}")

    # Verify
    raw = json.loads(RULESET_PATH.read_text())
    new_version = raw.get("version")
    print(f"\nPost-release version: {new_version}")
    print(f"Changelog entries: {len(raw.get('changelog', []))}")
    assert new_version != prev_version, (
        f"Version did not bump: still {new_version}"
    )

    # Check jurisdictions present
    jo = raw.get("jurisdiction_overrides", raw.get("jurisdictions", {}))
    if isinstance(jo, dict):
        for code in JURISDICTIONS:
            assert code in jo, f"{code} not found in jurisdiction overrides after merge!"
            print(f"{code}: present in jurisdiction overrides ✓")
    elif isinstance(jo, list):
        codes_present = {item.get("jurisdiction_code", item.get("code", "")) for item in jo}
        for code in JURISDICTIONS:
            assert code in codes_present, f"{code} not found in jurisdiction overrides after merge!"
            print(f"{code}: present in jurisdiction overrides ✓")
    else:
        raise AssertionError("Jurisdiction overrides are neither dict nor list")

    print("\nAll merges and release verified.")


if __name__ == "__main__":
    main()
