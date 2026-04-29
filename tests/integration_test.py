"""
End-to-end integration smoke test for FastAPI + banker dashboard.

Run:
    python tests/integration_test.py

This script:
1) starts uvicorn (backend.main:app) on 127.0.0.1:8000
2) waits 2 seconds for boot (then probes readiness)
3) verifies:
   a) GET /api/health
   b) GET /
   c) POST /api/auth/login
   d) GET /api/institutions (with token)
4) prints clear [PASS]/[FAIL] lines
5) always shuts down backend
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Any, Dict, Optional

import requests

BASE_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT = 8


def _load_test_user() -> Dict[str, str]:
    """Resolve login credentials, preferring user data from state module."""
    try:
        import kyc_dashboard.state as state

        for attr in ("USERS", "users", "DEFAULT_USERS", "default_users"):
            users = getattr(state, attr, None)
            if isinstance(users, dict) and users:
                first = next(iter(users.values()))
                if isinstance(first, dict) and first.get("username") and first.get("password"):
                    return {"username": str(first["username"]), "password": str(first["password"])}
    except Exception:
        pass

    try:
        from kyc_dashboard.main import load_users

        users = load_users()
        if isinstance(users, dict) and users:
            first = next(iter(users.values()))
            return {"username": str(first["username"]), "password": str(first["password"])}
    except Exception:
        pass

    return {"username": "admin", "password": "admin123"}


def _pass(name: str, detail: str = "") -> None:
    print(f"✅ [PASS] {name}" + (f" - {detail}" if detail else ""))


def _fail(name: str, detail: str = "") -> None:
    print(f"❌ [FAIL] {name}" + (f" - {detail}" if detail else ""))


def _start_backend() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_boot(proc: subprocess.Popen[str], min_wait_seconds: int = 2, max_wait_seconds: int = 10) -> bool:
    # Requirement: wait 2 seconds for boot.
    time.sleep(min_wait_seconds)

    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=1.5)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.4)
    return False


def run() -> int:
    backend = _start_backend()
    failures = 0
    token: Optional[str] = None

    try:
        ready = _wait_for_boot(backend)
        if not ready:
            failures += 1
            stderr = ""
            try:
                stderr = (backend.stderr.read() or "").strip()
            except Exception:
                pass
            _fail("Backend startup", stderr[-400:] if stderr else "backend did not become ready")
            print("\nDone.")
            return 1

        # a) GET /api/health
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=REQUEST_TIMEOUT)
            body = r.json() if "application/json" in r.headers.get("content-type", "") else {}
            if r.status_code == 200 and body.get("status") == "ok":
                _pass("GET /api/health", str(body))
            else:
                failures += 1
                _fail("GET /api/health", f"status={r.status_code}, body={body}")
        except requests.RequestException as ex:
            failures += 1
            _fail("GET /api/health", f"timeout/network error: {ex}")

        # b) GET /
        try:
            r = requests.get(f"{BASE_URL}/", timeout=REQUEST_TIMEOUT)
            text = r.text.lower()
            if r.status_code == 200 and "text/html" in r.headers.get("content-type", "") and "banker" in text:
                _pass("GET /", "HTML served and contains 'banker'")
            else:
                failures += 1
                _fail(
                    "GET /",
                    f"status={r.status_code}, content-type={r.headers.get('content-type')}, contains_banker={'banker' in text}",
                )
        except requests.RequestException as ex:
            failures += 1
            _fail("GET /", f"timeout/network error: {ex}")

        # c) POST /api/auth/login with valid credentials
        creds = _load_test_user()
        try:
            r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=REQUEST_TIMEOUT)
            body: Dict[str, Any] = r.json() if "application/json" in r.headers.get("content-type", "") else {}
            token = body.get("token") if isinstance(body, dict) else None
            if r.status_code == 200 and token:
                _pass("POST /api/auth/login", f"user={creds['username']} role={body.get('role')}")
            else:
                failures += 1
                _fail("POST /api/auth/login", f"status={r.status_code}, body={body}")
        except requests.RequestException as ex:
            failures += 1
            _fail("POST /api/auth/login", f"timeout/network error: {ex}")

        # d) GET /api/institutions with token
        try:
            headers = {"X-Token": token} if token else {}
            r = requests.get(f"{BASE_URL}/api/institutions", headers=headers, timeout=REQUEST_TIMEOUT)
            body = r.json() if "application/json" in r.headers.get("content-type", "") else None
            if r.status_code == 200 and isinstance(body, list):
                _pass("GET /api/institutions", f"count={len(body)}")
            else:
                failures += 1
                _fail("GET /api/institutions", f"status={r.status_code}, body={body}")
        except requests.RequestException as ex:
            failures += 1
            _fail("GET /api/institutions", f"timeout/network error: {ex}")

    finally:
        backend.terminate()
        try:
            backend.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend.kill()

    print("\nDone.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
