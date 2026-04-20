"""Root conftest.py — environment bootstrapping for the Codex test environment."""
import subprocess
import sys
import importlib
import os


def _ensure_pyyaml() -> None:
    """Copy pyyaml from apt into the active pyenv if not importable.

    The Codex environment blocks pip but ships python3-yaml via apt.
    This is idempotent — skips copy if yaml already importable.
    """
    try:
        importlib.import_module("yaml")
        return  # already available
    except ModuleNotFoundError:
        pass

    site_pkgs = next(
        p for p in sys.path
        if "site-packages" in p and sys.prefix in p
    )

    # Find the apt yaml package
    apt_yaml_candidates = [
        "/usr/lib/python3/dist-packages/yaml",
        "/usr/lib/python3.10/dist-packages/yaml",
    ]
    apt_yaml = next((p for p in apt_yaml_candidates if os.path.isdir(p)), None)
    if apt_yaml is None:
        raise RuntimeError("pyyaml not found in apt dist-packages — cannot bootstrap")

    dst_yaml = os.path.join(site_pkgs, "yaml")
    if not os.path.exists(dst_yaml):
        subprocess.run(["cp", "-r", apt_yaml, dst_yaml], check=True)

    # Copy the _yaml C extension
    result = subprocess.run(
        ["find", "/usr/lib/python3", "-name", "_yaml*.so"],
        capture_output=True, text=True,
    )
    for so_path in result.stdout.strip().splitlines():
        dst_so = os.path.join(site_pkgs, os.path.basename(so_path))
        if not os.path.exists(dst_so):
            subprocess.run(["cp", so_path, dst_so], check=True)

    # Force reimport
    importlib.invalidate_caches()


_ensure_pyyaml()
