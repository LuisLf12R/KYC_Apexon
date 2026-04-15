import json
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent / "config"


def load_generator_matrix() -> dict:
    path = CONFIG_DIR / "kyc_generator_matrix.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_constraint_catalog() -> dict:
    path = CONFIG_DIR / "kyc_constraint_catalog.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_scenario_archetypes() -> dict:
    path = CONFIG_DIR / "kyc_scenario_archetypes.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
