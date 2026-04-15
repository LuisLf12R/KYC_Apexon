from pathlib import Path

from benchmarks.generate_demo_portfolio import generate_demo_portfolio, get_raw_table_paths


def generate_and_get_manifest_path(size: int) -> Path:
    """
    Generate a demo portfolio of the given size.
    Returns the Path to scenario_manifest.jsonl.
    Also writes messy raw KYC CSVs to benchmarks/output/raw_kyc_tables/.
    """
    manifest_path_str = generate_demo_portfolio(size=size, run_id=None)
    return Path(manifest_path_str)


def get_generated_raw_tables() -> dict[str, Path]:
    """
    Return a dict of {table_stem: Path} for all raw messy CSVs
    produced by the last generate_demo_portfolio() call.
    """
    return get_raw_table_paths()
