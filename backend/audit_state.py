"""
backend/audit_state.py
-----------------------
Module-level singleton for the hash-chained AuditLogger.

The logger is lazily initialized with a system/anonymous user and replaced
with a real user context on every login via reinit_logger().
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from kyc_audit.logger import AuditLogger

_logger: Optional[AuditLogger] = None

_SYSTEM_USER: Dict[str, Any] = {
    "user_id": "system",
    "username": "system",
    "role": "system",
    "full_name": "System",
}


def get_logger() -> AuditLogger:
    """Return the current session logger, lazily initialising with safe defaults."""
    global _logger
    if _logger is None:
        _logger = AuditLogger(_SYSTEM_USER)
    return _logger


def reinit_logger(user_id: str, username: str, role: str) -> AuditLogger:
    """Create a fresh logger attributed to an authenticated user (call on login)."""
    global _logger
    _logger = AuditLogger(
        {
            "user_id": user_id,
            "username": username,
            "role": role,
            "full_name": username,
        }
    )
    return _logger


def get_audit_events() -> List[Dict[str, Any]]:
    """Return the list of events recorded by the current logger."""
    logger = get_logger()
    # The AuditLogger stores events in self.events; fall back gracefully.
    return (
        getattr(logger, "events", None)
        or getattr(logger, "_events", None)
        or getattr(logger, "audit_log", None)
        or getattr(logger, "_audit_log", None)
        or []
    )
