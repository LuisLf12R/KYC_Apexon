"""Add crs_fatca dimension_overrides to CAN, UAE, IND staging overlays."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rules.schema import JurisdictionOverlay

STAGING_DIR = Path("rules/staging")

CRS_FATCA_OVERRIDES = {
    "CAN": {
        "fatca_applicable_jurisdictions": ["CAN"],
        "crs_participating_jurisdictions": ["CAN"],
        "w8_w9_required_entity_types": ["corporation", "trust", "partnership"],
    },
    "UAE": {
        "fatca_applicable_jurisdictions": ["UAE"],
        "crs_participating_jurisdictions": ["UAE"],
        "w8_w9_required_entity_types": ["corporation", "trust", "partnership", "foundation"],
    },
    "IND": {
        "fatca_applicable_jurisdictions": ["IND"],
        "crs_participating_jurisdictions": ["IND"],
        "w8_w9_required_entity_types": ["corporation", "trust", "partnership"],
    },
}


def main():
    for code, crs_fatca_params in CRS_FATCA_OVERRIDES.items():
        path = STAGING_DIR / f"{code}.json"
        if not path.exists():
            print(f"WARNING: {path} does not exist — skipping")
            continue

        data = json.loads(path.read_text())

        if "dimension_overrides" not in data:
            data["dimension_overrides"] = {}

        if "crs_fatca" in data["dimension_overrides"]:
            print(f"{code}: crs_fatca already present — validating only")
        else:
            data["dimension_overrides"]["crs_fatca"] = crs_fatca_params
            print(f"{code}: added crs_fatca dimension_overrides")

        validated = JurisdictionOverlay.model_validate(data)
        round_tripped = validated.model_dump(mode="json")
        path.write_text(json.dumps(round_tripped, indent=2) + "\n")
        print(f"{code}: schema round-trip validation passed")

    print("Done.")


if __name__ == "__main__":
    main()
