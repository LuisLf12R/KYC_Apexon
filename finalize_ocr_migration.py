"""
Finalization utility for OCR migration (v1 -> v2).

Performs verification, cleanup, v2 wiring checks, import tests, cache cleanup,
and report generation in one script.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def print_header(text: str) -> None:
    """Print section header."""
    print(f"\n{'=' * 80}\n  {text}\n{'=' * 80}\n")


def print_status(icon: str, message: str) -> None:
    """Print status with icon (✓, ✗, ⚠, →)."""
    allowed = {"✓", "✗", "⚠", "→"}
    prefix = icon if icon in allowed else "→"
    print(f"{prefix} {message}")


class MigrationFinalizer:
    """Orchestrates final migration steps."""

    REQUIRED_V2_FILES = [
        "execution_engine.py",
        "ocr_extractor_v2.py",
        "ocr_handler.py",
        "script_cache_manager.py",
    ]
    OLD_V1_FILES = [
        "llm_code_generator.py",
        "llm_code_generator_v1_BACKUP.py",
        "execution_engine_v1_BACKUP.py",
        "execution_engine_v2.py",
        "test_extraction_v2.py",
    ]
    OLD_DIRS = ["_v1_backups", "__pycache__", ".pytest_cache"]

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.llm_path = self.project_root / "llm_integration"
        self.results: dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "project_root": str(self.project_root),
            "llm_path": str(self.llm_path),
            "verified_files": [],
            "missing_files": [],
            "identified_old_files": [],
            "identified_old_dirs": [],
            "deleted_files": [],
            "deleted_dirs": [],
            "deleted_pyc_files": [],
            "init_file_status": "unknown",
            "v2_code_check": {},
            "import_test": {},
            "final_py_files": [],
            "success": False,
        }

    def verify_v2_files(self) -> bool:
        """Check v2 files exist."""
        print_header("Step 1: Verify V2 Files")
        if not self.llm_path.exists():
            print_status("✗", f"Path not found: {self.llm_path}")
            self.results["missing_files"] = self.REQUIRED_V2_FILES.copy()
            return False

        all_found = True
        for fname in self.REQUIRED_V2_FILES:
            fpath = self.llm_path / fname
            if fpath.exists():
                size = fpath.stat().st_size
                print_status("✓", f"{fname}: Found ({size} bytes)")
                self.results["verified_files"].append(fname)
            else:
                print_status("✗", f"{fname}: Missing")
                self.results["missing_files"].append(fname)
                all_found = False

        if not all_found:
            print_status("⚠", "Missing required v2 files. Suggestion: git pull --force")
        return all_found

    def identify_old_files(self) -> tuple[list[Path], list[Path]]:
        """Find old v1 files and dirs to delete."""
        print_header("Step 2: Identify Old V1 Files")
        files_to_delete: list[Path] = []
        dirs_to_delete: list[Path] = []

        print("Files to delete:")
        for fname in self.OLD_V1_FILES:
            fpath = self.llm_path / fname
            if fpath.exists():
                print(f"  - {fname} ({fpath.stat().st_size} bytes)")
                files_to_delete.append(fpath)
                self.results["identified_old_files"].append(fname)
            else:
                print(f"  - {fname} (not found)")

        print("\nDirectories to delete:")
        for dname in self.OLD_DIRS:
            dpath = self.llm_path / dname
            if dpath.exists() and dpath.is_dir():
                print(f"  - {dname}/")
                dirs_to_delete.append(dpath)
                self.results["identified_old_dirs"].append(dname)
            else:
                print(f"  - {dname}/ (not found)")

        return files_to_delete, dirs_to_delete

    def cleanup_old_files(self, files_to_delete: list[Path]) -> int:
        """Delete v1 backups and clutter."""
        print_header("Step 3: Clean Up Old Files")
        deleted_count = 0
        for fpath in files_to_delete:
            try:
                fpath.unlink()
                print_status("✓", f"Deleted: {fpath.name}")
                self.results["deleted_files"].append(fpath.name)
                deleted_count += 1
            except Exception as exc:
                print_status("✗", f"Failed to delete {fpath.name}: {exc}")
        print_status("→", f"Total deleted: {deleted_count} files")
        return deleted_count

    def cleanup_old_dirs(self, dirs_to_delete: list[Path]) -> int:
        """Delete backup and cache directories."""
        print_header("Step 4: Cleanup Old Directories")
        deleted_count = 0
        for dpath in dirs_to_delete:
            try:
                shutil.rmtree(dpath)
                print_status("✓", f"Deleted: {dpath.name}/")
                self.results["deleted_dirs"].append(dpath.name)
                deleted_count += 1
            except Exception as exc:
                print_status("✗", f"Failed to delete {dpath.name}/: {exc}")
        print_status("→", f"Total deleted: {deleted_count} directories")
        return deleted_count

    def create_init_file(self) -> bool:
        """Create __init__.py if missing."""
        print_header("Step 5: Create/Verify __init__.py")
        init_file = self.llm_path / "__init__.py"
        try:
            if init_file.exists():
                size = init_file.stat().st_size
                print_status("✓", f"__init__.py exists ({size} bytes)")
                self.results["init_file_status"] = "exists"
                return True

            init_file.write_text(
                '"""LLM Integration Package - OCR + AI Analysis Pipeline (v2)"""\n',
                encoding="utf-8",
            )
            print_status("✓", "__init__.py created")
            self.results["init_file_status"] = "created"
            return True
        except Exception as exc:
            print_status("✗", f"Failed to create/verify __init__.py: {exc}")
            self.results["init_file_status"] = f"failed: {exc}"
            return False

    def verify_v2_code(self) -> bool:
        """Check execution_engine.py is v2."""
        print_header("Step 6: Verify V2 Code")
        exec_engine = self.llm_path / "execution_engine.py"
        if not exec_engine.exists():
            print_status("✗", "execution_engine.py missing")
            self.results["v2_code_check"] = {"found": False}
            return False

        try:
            content = exec_engine.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            print_status("✗", f"Unable to read execution_engine.py: {exc}")
            self.results["v2_code_check"] = {"found": True, "read_error": str(exc)}
            return False

        has_v2_import = "from llm_integration.ocr_extractor_v2 import OCRExtractor" in content
        has_v1_symbol = "LLMCodeGenerator" in content or "llm_code_generator" in content
        ok = has_v2_import and not has_v1_symbol

        if has_v2_import:
            print_status("✓", "execution_engine.py has OCRExtractor import")
        else:
            print_status("✗", "execution_engine.py missing OCRExtractor import")

        if has_v1_symbol:
            print_status("⚠", "v1 references found (LLMCodeGenerator/llm_code_generator)")
            print_status("⚠", "Manual replacement may be required.")
        else:
            print_status("✓", "No v1 references found")

        self.results["v2_code_check"] = {
            "found": True,
            "has_v2_import": has_v2_import,
            "has_v1_symbol": has_v1_symbol,
            "ok": ok,
        }
        return ok

    def test_import(self) -> bool:
        """Test that v2 imports and initializes."""
        print_header("Step 7: Test V2 Import")
        import_ok = False
        details: dict[str, Any] = {}

        try:
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))

            from llm_integration.execution_engine import ExecutionEngine  # noqa: PLC0415

            engine = ExecutionEngine()
            has_ocr_extractor = hasattr(engine, "ocr_extractor")
            has_cache_manager = hasattr(engine, "cache_manager")
            has_llm_generator = hasattr(engine, "llm_generator")

            print_status("✓", "ExecutionEngine imported successfully")
            print_status("✓", f"Has ocr_extractor: {has_ocr_extractor}")
            print_status("✓", f"Has cache_manager: {has_cache_manager}")
            print_status("✓", f"Has llm_generator: {has_llm_generator}")

            import_ok = has_ocr_extractor and (not has_cache_manager) and (not has_llm_generator)
            if import_ok:
                print_status("✓", "ExecutionEngine is v2 (correct!)")
            else:
                print_status("✗", "ExecutionEngine attribute checks indicate v1 mismatch.")

            details = {
                "imported": True,
                "has_ocr_extractor": has_ocr_extractor,
                "has_cache_manager": has_cache_manager,
                "has_llm_generator": has_llm_generator,
                "ok": import_ok,
            }
        except Exception as exc:
            print_status("✗", f"Import test failed: {exc}")
            print_status("⚠", "If this is environment-related, set credentials and retry.")
            details = {"imported": False, "error": str(exc), "ok": False}

        self.results["import_test"] = details
        return import_ok

    def clear_cache(self) -> int:
        """Delete __pycache__ and .pyc files."""
        print_header("Step 8: Clear Python Cache")
        deleted_dirs = 0
        deleted_pyc = 0

        for cache_dir in self.llm_path.rglob("__pycache__"):
            if cache_dir.is_dir():
                try:
                    shutil.rmtree(cache_dir)
                    deleted_dirs += 1
                    self.results["deleted_dirs"].append(str(cache_dir.relative_to(self.llm_path)))
                except Exception as exc:
                    print_status("⚠", f"Could not delete {cache_dir}: {exc}")

        for pyc_file in self.llm_path.rglob("*.pyc"):
            if pyc_file.is_file():
                try:
                    pyc_file.unlink()
                    deleted_pyc += 1
                    self.results["deleted_pyc_files"].append(
                        str(pyc_file.relative_to(self.llm_path))
                    )
                except Exception as exc:
                    print_status("⚠", f"Could not delete {pyc_file}: {exc}")

        print_status("✓", f"Cleared {deleted_dirs} __pycache__ directories")
        print_status("✓", f"Cleared {deleted_pyc} .pyc files")
        return deleted_dirs + deleted_pyc

    def show_final_structure(self) -> None:
        """List final file structure."""
        print_header("Step 9: Final Structure")
        py_files = sorted(self.llm_path.glob("*.py"))
        self.results["final_py_files"] = [f.name for f in py_files]

        if not py_files:
            print_status("⚠", "No .py files found under llm_integration/")
            return

        print("✓ Python files:")
        for f in py_files:
            size = f.stat().st_size
            if f.name in {"execution_engine.py", "ocr_extractor_v2.py"}:
                marker = "[v2]"
            elif f.name == "__init__.py":
                marker = "[pkg]"
            else:
                marker = "[util]"
            print(f"  {marker} {f.name} ({size} bytes)")

        print_status("✓", f"Total: {len(py_files)} files")

    def generate_report(self) -> None:
        """Create MIGRATION_COMPLETE.txt."""
        report_path = self.project_root / "MIGRATION_COMPLETE.txt"
        lines = [
            "OCR Migration Finalization Report",
            "=" * 40,
            f"Timestamp (UTC): {self.results['timestamp_utc']}",
            f"Project root: {self.results['project_root']}",
            f"LLM path: {self.results['llm_path']}",
            "",
            f"Verified v2 files: {self.results['verified_files']}",
            f"Missing v2 files: {self.results['missing_files']}",
            f"Deleted files: {self.results['deleted_files']}",
            f"Deleted dirs: {self.results['deleted_dirs']}",
            f"Deleted pyc files: {self.results['deleted_pyc_files']}",
            f"__init__.py status: {self.results['init_file_status']}",
            f"V2 code check: {self.results['v2_code_check']}",
            f"Import test: {self.results['import_test']}",
            f"Final .py files: {self.results['final_py_files']}",
            f"Overall success: {self.results['success']}",
            "",
            "Next steps:",
            "1) Restart Streamlit",
            "   taskkill /F /IM python.exe",
            "   streamlit run your_app.py",
            "2) Test with passport image",
            "3) Verify no 'document_type' error",
        ]
        try:
            report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print_status("✓", f"Report generated: {report_path.name}")
        except Exception as exc:
            print_status("✗", f"Failed to generate report: {exc}")

    def run_all(self) -> bool:
        """Execute all steps in order."""
        print_header("FINALIZE OCR MIGRATION: v1 → v2")
        print(f"Project: {self.project_root}")
        print(f"LLM Integration: {self.llm_path}")

        if not self.verify_v2_files():
            self.generate_report()
            return False

        files_to_delete, dirs_to_delete = self.identify_old_files()
        self.cleanup_old_files(files_to_delete)
        self.cleanup_old_dirs(dirs_to_delete)
        self.create_init_file()
        self.verify_v2_code()
        import_ok = self.test_import()
        self.clear_cache()
        self.show_final_structure()

        self.results["success"] = bool(
            self.results.get("v2_code_check", {}).get("ok") and import_ok
        )

        print_header("FINALIZE COMPLETE ✓" if self.results["success"] else "FINALIZE COMPLETE ⚠")
        if self.results["success"]:
            print("Summary:")
            print("✓ V2 files verified")
            print("✓ Old v1 files/clutter deleted")
            print("✓ __init__.py verified")
            print("✓ V2 code verified")
            print("✓ Import test passed")
            print("✓ Cache cleared")
        else:
            print("Summary:")
            print("⚠ Migration finalized with warnings. Check report for details.")

        print("\nIMMEDIATE NEXT STEPS:")
        print("1. RESTART YOUR APP:")
        print("   taskkill /F /IM python.exe")
        print("   streamlit run your_app.py")
        print("2. TEST WITH PASSPORT IMAGE")
        print("3. VERIFY no 'document_type' error")

        self.generate_report()
        return self.results["success"]


def main() -> int:
    """Main entry point."""
    project_root = Path(__file__).resolve().parent
    finalizer = MigrationFinalizer(project_root=project_root)
    ok = finalizer.run_all()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
