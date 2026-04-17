"""
Cleanup and push helper for llm_integration/.

This script removes legacy v1 files/caches and keeps only the expected
v2 production-oriented module set in llm_integration/.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

FILES_TO_KEEP = {
    "execution_engine.py",
    "ocr_extractor_v2.py",
    "ocr_handler.py",
    "script_cache_manager.py",
    "__init__.py",
}

FILES_TO_DELETE = {
    "execution_engine_v1_BACKUP.py",
    "execution_engine_v2.py",
    "llm_code_generator.py",
    "llm_code_generator_v1_BACKUP.py",
    "test_extraction_v2.py",
    "llm_integration.py",
}

DIRS_TO_DELETE = {"_v1_backups", "__pycache__", ".pytest_cache"}


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), check=check, capture_output=True, text=True)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parent.parent


def print_header(text: str) -> None:
    print(f"\n{'=' * 80}\n{text}\n{'=' * 80}")


def delete_path(path: Path, dry_run: bool) -> bool:
    if not path.exists():
        print(f"⚠ Not found (ok): {path.name}")
        return False
    if dry_run:
        print(f"→ Would delete: {path.name}")
        return True
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    print(f"✓ Deleted: {path.name}")
    return True


def ensure_required_files(llm_dir: Path) -> bool:
    print_header("Validate required v2 files")
    required = FILES_TO_KEEP - {"__init__.py"}
    missing = []
    for fname in sorted(FILES_TO_KEEP):
        exists = (llm_dir / fname).exists()
        marker = "✓" if exists else ("⚠" if fname == "__init__.py" else "✗")
        print(f"{marker} {fname}")
        if fname in required and not exists:
            missing.append(fname)
    if missing:
        print(f"✗ Missing required files: {', '.join(missing)}")
        return False
    return True


def create_init_if_missing(llm_dir: Path, dry_run: bool) -> None:
    init_file = llm_dir / "__init__.py"
    if init_file.exists():
        print("✓ __init__.py already exists")
        return
    if dry_run:
        print("→ Would create __init__.py")
        return
    init_file.write_text('"""LLM Integration package."""\n', encoding="utf-8")
    print("✓ Created __init__.py")


def git_commit_and_optional_push(project_root: Path, message: str, push: bool, dry_run: bool) -> None:
    print_header("Git status")
    status = run(["git", "status", "--short"], cwd=project_root, check=False)
    if status.returncode != 0:
        print("⚠ Git unavailable or not a repository.")
        return
    print(status.stdout.rstrip() or "✓ Working tree clean")
    if dry_run:
        print("→ Dry run enabled; skipping commit/push.")
        return

    run(["git", "add", "-A"], cwd=project_root)
    commit = run(["git", "commit", "-m", message], cwd=project_root, check=False)
    if commit.returncode == 0:
        print(f"✓ Committed: {message}")
    elif "nothing to commit" in (commit.stdout + commit.stderr).lower():
        print("✓ Nothing to commit.")
        return
    else:
        print(f"✗ Commit failed:\n{commit.stderr.strip()}")
        return

    if push:
        pushed = run(["git", "push"], cwd=project_root, check=False)
        if pushed.returncode == 0:
            print("✓ Pushed to remote.")
        else:
            print(f"⚠ Push warning:\n{pushed.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup llm_integration and optionally commit/push.")
    parser.add_argument("--project-root", type=Path, default=repo_root_from_script())
    parser.add_argument(
        "--commit-message",
        default="chore: cleanup llm_integration - keep only v2 production files",
    )
    parser.add_argument("--push", action="store_true", help="Push to remote after commit")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without changing files")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    llm_dir = project_root / "llm_integration"

    print_header("LLM Integration cleanup")
    print(f"Project root: {project_root}")
    print(f"Target path : {llm_dir}")
    if not llm_dir.exists():
        print(f"✗ Target path does not exist: {llm_dir}")
        return 1

    if not ensure_required_files(llm_dir):
        return 1

    print_header("Delete old files")
    for fname in sorted(FILES_TO_DELETE):
        delete_path(llm_dir / fname, dry_run=args.dry_run)

    print_header("Delete old directories")
    for dname in sorted(DIRS_TO_DELETE):
        delete_path(llm_dir / dname, dry_run=args.dry_run)

    print_header("Ensure package init")
    create_init_if_missing(llm_dir, dry_run=args.dry_run)

    git_commit_and_optional_push(
        project_root=project_root,
        message=args.commit_message,
        push=args.push,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
