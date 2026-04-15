from pathlib import Path

from benchmarks.generate_demo_portfolio import generate_demo_portfolio


def generate_and_get_manifest_path(size: int) -> Path:
    """
    Generate a demo portfolio of the given size and return the Path
    to the scenario_manifest.jsonl file.
    """
    manifest_path_str = generate_demo_portfolio(size=size, run_id=None, output_path=None)
    return Path(manifest_path_str)
