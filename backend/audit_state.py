"""
backend/audit_state.py
-----------------------
Module-level singleton for the hash-chained AuditLogger.

The logger is lazily initialized with a system/anonymous user and replaced
with a real user context on every login via reinit_logger().
"""
from __future__ import annotations

import logging as _logging
from typing import Any, Dict, List, Optional

from kyc_audit.logger import AuditLogger

_log = _logging.getLogger(__name__)

_logger: Optional[AuditLogger] = None

_SYSTEM_USER: Dict[str, Any] = {
    "user_id": "usr_demo_admin",
    "username": "admin",
    "role": "Admin",
    "full_name": "M. Lyons",
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
    for attr in ("events", "_events", "audit_log", "_audit_log"):
        val = getattr(logger, attr, None)
        if val is not None:
            return list(val)
    _log.warning(
        "AuditLogger has no recognised events attribute (%s); audit data unavailable",
        type(logger).__name__,
    )
    return []
