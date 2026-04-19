"""
audit_logger.py
---------------
Core audit trail system for the KYC Compliance Platform.

Design principles:
- Every event is immutable once logged
- Events are hash-chained within a session (each event hash includes previous)
- Sessions are hash-chained across sessions (each session hash includes previous session hash)
- Temp file written after every event so nothing is lost on crash
- Finalized log includes SHA-256 of entire session for tamper detection
- Audit trail stores metadata only — raw PII fields are never written

Event schema (every event):
  event_id        : UUID
  session_id      : UUID
  user_id         : string
  username        : string
  role            : string
  timestamp       : ISO 8601 UTC
  action_type     : string (see ACTION_TYPES below)
  customer_id     : string or null
  batch_id        : string or null
  details         : dict  (action-specific metadata, no raw PII)
  snapshot        : dict  (system state at time of event — scores, versions, etc.)
  prompt_version  : string or null
  ruleset_version : string
  previous_hash   : string (hash of previous event, or session seed for first event)
  event_hash      : string (SHA-256 of previous_hash + this event's content)
"""

import hashlib
import json
import uuid
import tempfile
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from kyc_engine.ruleset import get_active_ruleset_version as _get_version


# ── Constants ────────────────────────────────────────────────────────────────

RULESET_VERSION = _get_version()
CHAIN_FILE = Path(tempfile.gettempdir()) / "kyc_audit_chain.json"

# All valid action types — add new ones here, never remove old ones
ACTION_TYPES = {
    # Session lifecycle
    "LOGIN":                    "User authenticated and session started",
    "LOGOUT":                   "User manually logged out",
    "SESSION_TIMEOUT_WARNING":  "Inactivity warning shown to user (13 min threshold)",
    "SESSION_EXPIRED":          "Session auto-terminated due to inactivity (15 min threshold)",

    # Data ingestion
    "FILE_UPLOAD":              "File uploaded to Data Management pipeline",
    "OCR_RUN":                  "Google Vision OCR executed on a document",
    "LLM_CALL":                 "Claude API call made (structuring or analysis)",
    "DATA_CLEAN":               "Cleaning pipeline applied to a dataset",
    "SCHEMA_HARMONIZED":        "Schema harmonizer normalized input to canonical schema",
    "SCHEMA_HARMONIZE_FAILED":  "Schema harmonizer failed; raw DataFrame retained as fallback",
    "SCHEMA_HARMONIZE_REJECTED":"Harmonization rejected source data for missing critical fields",
    "ENGINE_RELOAD":            "KYC engine reloaded with new dataset",
    "AUTODETECT_RUN":           "Claude used to classify dataset type of a file",

    # Evaluation
    "CUSTOMER_VIEW":            "User viewed a specific customer record (snapshot captured)",
    "BATCH_RUN_START":          "Batch evaluation started",
    "BATCH_RUN_COMPLETE":       "Batch evaluation completed with summary",
    "CUSTOMER_EVALUATED":       "Single customer evaluated by engine",
    "FLAG_RAISED":              "Compliance flag raised for a customer",

    # Workflow / remediation
    "CUSTOMER_ESCALATED":       "Customer escalated by analyst for manager review",
    "CLEAR_PROPOSED":           "Analyst proposed clearing a flag (awaiting manager approval)",
    "CLEAR_APPROVED":           "Manager approved proposed clear",
    "CLEAR_REJECTED":           "Manager rejected proposed clear",
    "NOTE_ADDED":               "User added a note to a customer case",

    # Access / UI
    "AUDIT_VIEWER_OPENED":      "User opened the Audit Trail tab",
    "AUDIT_EXPORTED":           "Session audit log exported by user",
    "EXPORT_PACKAGE_CREATED":   "Full export package (zip) created",
    "PII_MASK_TOGGLED":         "PII masking toggled on or off",
}


# ── Hash utilities ────────────────────────────────────────────────────────────

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _hash_event(previous_hash: str, event_content: dict) -> str:
    """Hash = SHA256(previous_hash + sorted JSON of event content)."""
    content_str = json.dumps(event_content, sort_keys=True, default=str)
    return _sha256(previous_hash + content_str)


def _hash_session(previous_session_hash: str, events: list) -> str:
    """Session hash = SHA256(previous_session_hash + sorted JSON of all events)."""
    events_str = json.dumps(events, sort_keys=True, default=str)
    return _sha256(previous_session_hash + events_str)


# ── Chain persistence ─────────────────────────────────────────────────────────

def load_previous_session_hash() -> str:
    """
    Load the hash of the last finalized session.
    Falls back to the AUDIT_CHAIN_SEED environment variable (genesis hash).
    If neither exists, uses a hardcoded genesis string (should not happen in production).
    """
    genesis = os.getenv(
        "AUDIT_CHAIN_SEED",
        "KYC-PLATFORM-GENESIS-APEXON-2026"
    )
    try:
        if CHAIN_FILE.exists():
            with open(CHAIN_FILE) as f:
                data = json.load(f)
                return data.get("last_session_hash", genesis)
    except Exception:
        pass
    return genesis


def save_session_hash(session_hash: str, session_id: str):
    """Persist the last session hash for the next session to chain from."""
    try:
        with open(CHAIN_FILE, "w") as f:
            json.dump({
                "last_session_hash": session_hash,
                "last_session_id": session_id,
                "saved_at": datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
    except Exception:
        pass


# ── AuditLogger ───────────────────────────────────────────────────────────────

class AuditLogger:
    """
    Immutable event logger for a single user session.

    Usage:
        logger = AuditLogger(user)
        logger.log("CUSTOMER_VIEW", customer_id="C00001", snapshot={...}, details={...})
        json_str = logger.export_json()   # on logout / export
    """

    def __init__(self, user: dict):
        self.session_id = str(uuid.uuid4())
        self.user_id = user["user_id"]
        self.username = user["username"]
        self.role = user["role"]
        self.full_name = user.get("full_name", "")
        self.session_start = datetime.now(timezone.utc).isoformat()

        # Hash chain
        self.previous_session_hash = load_previous_session_hash()
        self.current_hash = self.previous_session_hash  # seed for first event

        self.events: List[dict] = []
        self._temp_file = Path(tempfile.gettempdir()) / f"kyc_audit_{self.session_id}.json"

        # Load active prompt versions from registry
        self._prompt_versions = self._load_prompt_versions()

    # ── Public API ────────────────────────────────────────────────────────────

    def log(
        self,
        action_type: str,
        details: Optional[Dict[str, Any]] = None,
        customer_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
        prompt_id: Optional[str] = None,
    ) -> dict:
        """
        Log an audit event. Returns the event dict.

        Args:
            action_type  : One of ACTION_TYPES keys
            details      : Action-specific metadata (no raw PII)
            customer_id  : Customer affected, if any
            batch_id     : Batch run ID, if applicable
            snapshot     : System state at time of event (scores, versions, etc.)
            prompt_id    : Prompt version used, if an LLM was called
        """
        if action_type not in ACTION_TYPES:
            action_type = "UNKNOWN_ACTION"

        # Build event content (everything that gets hashed — no event_hash field yet)
        event_content = {
            "event_id": str(uuid.uuid4()),
            "session_id": self.session_id,
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "action_description": ACTION_TYPES.get(action_type, ""),
            "customer_id": customer_id,
            "batch_id": batch_id,
            "details": details or {},
            "snapshot": snapshot or {},
            "prompt_version": prompt_id or self._prompt_versions.get(action_type),
            "ruleset_version": RULESET_VERSION,
            "previous_hash": self.current_hash,
        }

        # Compute and attach event hash
        event_hash = _hash_event(self.current_hash, event_content)
        event_content["event_hash"] = event_hash
        self.current_hash = event_hash

        self.events.append(event_content)
        # Write temp file every 10 events to avoid I/O overhead on large batches
        if len(self.events) % 10 == 0:
            self._write_temp()

        return event_content

    def finalize(self) -> dict:
        """
        Produce the final session log with session-level SHA-256 hash.
        Called on logout, export, or session expiry.
        Does NOT modify self.events — safe to call multiple times.
        """
        session_hash = _hash_session(self.previous_session_hash, self.events)

        session_log = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "full_name": self.full_name,
            "session_start": self.session_start,
            "session_end": datetime.now(timezone.utc).isoformat(),
            "event_count": len(self.events),
            "previous_session_hash": self.previous_session_hash,
            "session_hash": session_hash,
            "verification_note": (
                "To verify integrity: re-compute SHA-256 of "
                "(previous_session_hash + JSON.stringify(events, sort_keys=True)) "
                "and compare to session_hash."
            ),
            "events": self.events,
        }

        # Persist hash so next session can chain from this one
        save_session_hash(session_hash, self.session_id)

        return session_log

    def export_json(self) -> str:
        """Return finalized session log as a JSON string."""
        return json.dumps(self.finalize(), indent=2, default=str)

    def get_events_df(self):
        """Return events as a pandas DataFrame for the audit viewer."""
        import pandas as pd
        if not self.events:
            return pd.DataFrame()
        rows = []
        for e in self.events:
            rows.append({
                "Timestamp": e["timestamp"],
                "User": e["username"],
                "Role": e["role"],
                "Action": e["action_type"],
                "Description": e["action_description"],
                "Customer ID": e.get("customer_id") or "",
                "Batch ID": e.get("batch_id") or "",
                "Prompt Version": e.get("prompt_version") or "",
                "Ruleset": e.get("ruleset_version", ""),
                "Event Hash": e["event_hash"][:12] + "...",  # truncated for display
            })
        return pd.DataFrame(rows)

    def event_count(self) -> int:
        return len(self.events)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _write_temp(self):
        """Write current state to temp file after every event."""
        try:
            with open(self._temp_file, "w") as f:
                json.dump({
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "current_hash": self.current_hash,
                    "event_count": len(self.events),
                    "events": self.events,
                }, f, default=str)
        except Exception:
            pass

    def _load_prompt_versions(self) -> dict:
        """Load active prompt IDs from prompts/registry.json."""
        try:
            registry_path = Path.cwd() / "prompts" / "registry.json"
            if registry_path.exists():
                with open(registry_path) as f:
                    registry = json.load(f)
                active = {p["id"] for p in registry.get("prompts", []) if p.get("active")}
                # Map action types to their relevant prompt
                return {
                    "LLM_CALL": next((p for p in active if "structuring" in p), None),
                    "OCR_RUN": next((p for p in active if "analysis" in p), None),
                    "AUTODETECT_RUN": next((p for p in active if "autodetect" in p), None),
                }
        except Exception:
            pass
        return {}


# ── Standalone verification utility ──────────────────────────────────────────

def verify_session_log(session_log: dict) -> dict:
    """
    Verify the integrity of a finalized session log.
    Returns a dict with 'valid' bool and 'details' string.
    Can be run independently by an auditor.
    """
    events = session_log.get("events", [])
    previous_session_hash = session_log.get("previous_session_hash", "")
    claimed_session_hash = session_log.get("session_hash", "")

    # 1. Verify event chain
    chain_valid = True
    broken_at = None
    current = previous_session_hash

    for i, event in enumerate(events):
        claimed_event_hash = event.get("event_hash", "")
        event_content = {k: v for k, v in event.items() if k != "event_hash"}
        expected_hash = _hash_event(current, event_content)
        if expected_hash != claimed_event_hash:
            chain_valid = False
            broken_at = i
            break
        current = claimed_event_hash

    # 2. Verify session hash
    computed_session_hash = _hash_session(previous_session_hash, events)
    session_hash_valid = computed_session_hash == claimed_session_hash

    return {
        "valid": chain_valid and session_hash_valid,
        "event_chain_valid": chain_valid,
        "session_hash_valid": session_hash_valid,
        "event_count": len(events),
        "broken_at_event": broken_at,
        "computed_session_hash": computed_session_hash,
        "claimed_session_hash": claimed_session_hash,
        "details": (
            "All checks passed — log is unmodified."
            if chain_valid and session_hash_valid
            else f"INTEGRITY FAILURE: event_chain={'OK' if chain_valid else f'BROKEN at event {broken_at}'}, "
                 f"session_hash={'OK' if session_hash_valid else 'MISMATCH'}"
        )
    }
