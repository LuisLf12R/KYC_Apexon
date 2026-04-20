"""
init_state.py — seed fetch_state.yaml from registry.yaml.

Behaviour
---------
- Loads registry.yaml (validated).
- Skips inactive sources (active=False).
- For each active source and each of its URLs, inserts a blank UrlState
  into fetch_state.yaml ONLY if that (source_id, url_label) pair does not
  already exist — safe to re-run without overwriting live fetch data.
- Writes the result back to fetch_state.yaml.
- Prints a summary of entries added vs already present.

Usage
-----
  python -m sources.fetcher.init_state
  python -m sources.fetcher.init_state --registry path/to/registry.yaml \n                                        --state    path/to/fetch_state.yaml
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from sources.schema.registry import load_registry
from sources.schema.fetch_state import UrlState, load_fetch_state, save_fetch_state


def init_state(
    registry_path: str | os.PathLike | None = None,
    state_path: str | os.PathLike | None = None,
) -> dict:
    """Seed fetch_state from registry. Returns summary dict."""
    registry = load_registry(registry_path)
    manifest = load_fetch_state(state_path)

    added = 0
    already_present = 0

    for source in registry.sources:
        if not source.active:
            continue
        if source.id not in manifest.states:
            manifest.states[source.id] = {}
        for url_entry in source.urls:
            if url_entry.label not in manifest.states[source.id]:
                manifest.states[source.id][url_entry.label] = UrlState()
                added += 1
            else:
                already_present += 1

    # Refresh generated_at timestamp
    manifest.generated_at = datetime.utcnow().isoformat()

    save_fetch_state(manifest, state_path)

    return {
        "active_sources": sum(1 for s in registry.sources if s.active),
        "added": added,
        "already_present": already_present,
        "state_path": str(state_path) if state_path else "sources/fetch_state.yaml",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fetch_state.yaml from registry.yaml")
    parser.add_argument("--registry", default=None, help="Path to registry.yaml")
    parser.add_argument("--state", default=None, help="Path to fetch_state.yaml")
    args = parser.parse_args()

    summary = init_state(registry_path=args.registry, state_path=args.state)
    print(f"Active sources : {summary['active_sources']}")
    print(f"Entries added  : {summary['added']}")
    print(f"Already present: {summary['already_present']}")
    print(f"State written  : {summary['state_path']}")


if __name__ == "__main__":
    main()
