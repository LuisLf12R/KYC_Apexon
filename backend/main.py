from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.ai_observability import get_tracker as get_ai_tracker
from backend.audit_state import get_logger, reinit_logger, get_audit_events
from backend.pipeline import process_file
from backend.utils import _format_results, _get_institutions, _load_temp_dfs

from kyc_engine.engine import KYCComplianceEngine

DATA_DIR = Path(tempfile.gettempdir()) / "kyc_data_clean"
RULES_DIR = Path(__file__).parent.parent / "rules"
API_BASE_URL = os.getenv("API_BASE_URL", "")

# In-memory document vault: filename → (bytes, mime_type)
_DOC_VAULT: Dict[str, tuple] = {}


def _load_users() -> Dict[str, Dict[str, Any]]:
    """Load users from users.json at repo root."""
    users_json = Path(__file__).parent.parent / "users.json"
    try:
        data = json.loads(users_json.read_text(encoding="utf-8"))
        return {
            u["username"].lower(): u
            for u in data.get("users", [])
            if u.get("username")
        }
    except Exception:
        return {
            "admin": {
                "user_id": "usr_admin_001",
                "username": "admin",
                "password": "admin123",
                "role": "Admin",
                "full_name": "M. Lyons",
            },
            "banker": {
                "user_id": "usr_banker_001",
                "username": "banker",
                "password": "banker123",
                "role": "Banker",
                "full_name": "J. Marlow",
            },
        }


USERS = _load_users()
SESSIONS: Dict[str, Dict[str, Any]] = {}
# In-memory approval overrides: customer_id → "approved" | "rejected"
# Ephemeral — clears on server restart (acceptable for demo).
APPROVALS: Dict[str, str] = {}

app = FastAPI(title="KYC Backend API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/admin")
def admin_redirect():
    return RedirectResponse(url="/", status_code=302)



class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: str
    message: str


class LogoutRequest(BaseModel):
    token: str


class MessageResponse(BaseModel):
    message: str


class KYCBatchRequest(BaseModel):
    institution_id: Optional[str] = None


class KYCBatchResponse(BaseModel):
    results: list[dict[str, Any]]
    summary: dict[str, int]


class KYCCustomerResponse(BaseModel):
    result: dict[str, Any]


class UploadResult(BaseModel):
    filename: str
    dataset_type: Optional[str]
    rows: int
    status: str
    message: str


class UploadResponse(BaseModel):
    results: list[UploadResult]
    total_rows: int
    errors: int


class ApprovalResponse(BaseModel):
    customer_id: str
    action: str
    message: str


def _extract_token(
    authorization: Optional[str], x_token: Optional[str], token: Optional[str]
) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if x_token:
        return x_token.strip()
    if token:
        return token.strip()
    return None


def _require_session(
    authorization: Optional[str] = Header(default=None),
    x_token: Optional[str] = Header(default=None, alias="X-Token"),
    token: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    resolved = _extract_token(authorization, x_token, token)
    if not resolved or resolved not in SESSIONS:
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")
    return SESSIONS[resolved]


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    print(f"[LOGIN] attempt username={payload.username!r}")
    key = payload.username.strip().lower()
    user = USERS.get(key)

    if not user or user.get("password") != payload.password:
        print(f"[LOGIN] invalid credentials username={payload.username!r}")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = str(uuid.uuid4())
    SESSIONS[token] = {
        "token": token,
        "username": user.get("username", key),
        "role": user.get("role", "banker").lower(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    print(f"[LOGIN] success username={payload.username!r} role={SESSIONS[token]['role']}")
    reinit_logger(
        user_id=user.get("user_id", key),
        username=user.get("username", key),
        role=SESSIONS[token]["role"],
    )
    get_logger().log("LOGIN", customer_id=None, details={"username": key})
    return LoginResponse(token=token, role=SESSIONS[token]["role"], message="Login successful")


@app.post("/api/auth/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest) -> MessageResponse:
    print("[LOGOUT] request")
    get_logger().log("LOGOUT", customer_id=None, details={})
    SESSIONS.pop(payload.token, None)
    return MessageResponse(message="Logged out")


@app.get("/api/health")
def health() -> Dict[str, str]:
    print("[HEALTH] check")
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/institutions")
def institutions() -> list[dict[str, str]]:
    print("[INSTITUTIONS] fetch")
    return _get_institutions()


@app.post("/api/kyc/batch", response_model=KYCBatchResponse)
def kyc_batch(
    payload: KYCBatchRequest,
) -> KYCBatchResponse:
    print(f"[KYC_BATCH] institution_id={payload.institution_id!r}")
    dfs = _load_temp_dfs()
    customers_df = dfs.get("customers", pd.DataFrame())

    if customers_df.empty:
        raise HTTPException(status_code=404, detail="No customers dataset loaded")
    if "customer_id" not in customers_df.columns:
        raise HTTPException(status_code=500, detail="customers dataset missing customer_id")

    filtered_df = customers_df.copy()
    if payload.institution_id:
        for col in ("institution_id", "institution"):
            if col in filtered_df.columns:
                filtered_df = filtered_df[filtered_df[col].astype(str) == payload.institution_id]
                break

    customer_ids = filtered_df["customer_id"].dropna().astype(str).unique().tolist()
    if not customer_ids:
        return KYCBatchResponse(results=[], summary={"total": 0, "flagged": 0})

    batch_id = f"batch_{uuid.uuid4().hex[:8]}"
    get_logger().log("BATCH_RUN_START", batch_id=batch_id, details={
        "institution_id": payload.institution_id,
        "total_customers": len(customer_ids),
    })

    engine = KYCComplianceEngine(data_clean_dir=DATA_DIR)
    evaluations = []
    for cid in customer_ids:
        try:
            evaluations.append(engine.evaluate_customer(cid, institution_id=payload.institution_id))
        except Exception as ex:
            print(f"[KYC_BATCH] evaluation error customer_id={cid!r}: {ex}")

    formatted = _format_results(evaluations, customers_df, dfs)
    flagged = sum(1 for r in evaluations if str(r.get("disposition", "")).upper() != "PASS")
    get_logger().log("BATCH_RUN_COMPLETE", batch_id=batch_id, details={
        "institution_id": payload.institution_id,
        "total": len(evaluations),
        "flagged": flagged,
    })
    # Apply manual approval overrides to batch results
    for case in formatted.get("cases", []):
        cid = case.get("id")
        if not cid:
            continue
        override = APPROVALS.get(cid)
        if override == "approved":
            case["status"] = "Cleared"
            case["sla"]    = {"tone": "ok", "label": "Approved"}
        elif override == "rejected":
            case["status"] = "Escalated"
            case["sla"]    = {"tone": "bad", "label": "Rejected"}
    return KYCBatchResponse(
        results=formatted.get("cases", []),
        summary={"total": len(evaluations), "flagged": flagged},
    )


@app.get("/api/kyc/customer/{customer_id}", response_model=KYCCustomerResponse)
def kyc_customer(
    customer_id: str,
    _: Dict[str, Any] = Depends(_require_session),
) -> KYCCustomerResponse:
    print(f"[KYC_CUSTOMER] customer_id={customer_id!r}")
    dfs = _load_temp_dfs()
    customers_df = dfs.get("customers", pd.DataFrame())

    if customers_df.empty or "customer_id" not in customers_df.columns:
        raise HTTPException(status_code=404, detail="Customer dataset unavailable")

    customer_mask = customers_df["customer_id"].astype(str) == str(customer_id)
    if not customer_mask.any():
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    engine = KYCComplianceEngine(data_clean_dir=DATA_DIR)
    institution_id = None
    customer_row = customers_df[customer_mask].iloc[0]
    if "institution_id" in customer_row.index:
        institution_id = str(customer_row.get("institution_id") or "").strip() or None

    result = engine.evaluate_customer(str(customer_id), institution_id=institution_id)
    formatted = _format_results([result], customers_df, dfs)
    cases = formatted.get("cases", [])
    if not cases:
        raise HTTPException(status_code=500, detail="Unable to format customer result")

    return KYCCustomerResponse(result=cases[0])


@app.post("/api/kyc/approve/{customer_id}", response_model=ApprovalResponse)
def approve_case(
    customer_id: str,
    session: Dict[str, Any] = Depends(_require_session),
) -> ApprovalResponse:
    if session.get("role") not in ("admin",):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    APPROVALS[customer_id] = "approved"
    get_logger().log("CLEAR_APPROVED", customer_id=customer_id, details={
        "approved_by": session.get("username"),
        "role": session.get("role"),
    })
    print(f"[APPROVE] customer_id={customer_id!r} by={session.get('username')!r}")
    return ApprovalResponse(customer_id=customer_id, action="approved", message="Case approved")


@app.post("/api/kyc/reject/{customer_id}", response_model=ApprovalResponse)
def reject_case(
    customer_id: str,
    session: Dict[str, Any] = Depends(_require_session),
) -> ApprovalResponse:
    if session.get("role") not in ("admin",):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    APPROVALS[customer_id] = "rejected"
    get_logger().log("CLEAR_REJECTED", customer_id=customer_id, details={
        "rejected_by": session.get("username"),
        "role": session.get("role"),
    })
    print(f"[REJECT] customer_id={customer_id!r} by={session.get('username')!r}")
    return ApprovalResponse(customer_id=customer_id, action="rejected", message="Case rejected")


@app.post("/api/upload", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    dataset_type: Optional[str] = None,
) -> UploadResponse:
    print(f"[UPLOAD] {len(files)} file(s)")
    results = []
    for f in files:
        raw = await f.read()
        fname = f.filename or "upload"
        ext = Path(fname).suffix.lower()
        mime = "application/pdf" if ext == ".pdf" else f"image/{ext.lstrip('.')}" if ext in {".png",".jpg",".jpeg",".gif"} else "application/octet-stream"
        _DOC_VAULT[fname] = (raw, mime)
        result = process_file(raw, fname, dataset_type or None)
        results.append(UploadResult(**result))
        print(f"[UPLOAD] {f.filename!r} → {result['status']} ({result['rows']} rows)")
    for result in results:
        if result.status == "ok":
            get_logger().log("FILE_UPLOAD", customer_id=None, details={
                "filename": result.filename,
                "dataset_type": result.dataset_type,
                "rows": result.rows,
            })
    total_rows = sum(r.rows for r in results)
    errors = sum(1 for r in results if r.status in ("error", "rejected"))
    return UploadResponse(results=results, total_rows=total_rows, errors=errors)


@app.get("/api/audit")
def audit_trail() -> Dict[str, Any]:
    """Return real hash-chained audit events from the current session."""
    print("[AUDIT] fetch")
    events = get_audit_events()
    logs = []
    for i, e in enumerate(events):
        action = e.get("action_type", "")
        event_hash = e.get("event_hash", "") or ""
        prev_hash  = events[i - 1].get("event_hash", "") if i > 0 else ""
        next_hash  = events[i + 1].get("event_hash", "") if i < len(events) - 1 else ""
        logs.append({
            "id":            e.get("event_id", f"evt_{i:04d}"),
            "timestamp":     e.get("timestamp", ""),
            "user":          e.get("username", ""),
            "role":          e.get("role", "analyst").capitalize(),
            "action":        action,
            "actionGroup":   _action_group(action),
            "description":   _format_audit_description(e),
            "customerId":    e.get("customer_id") or "",
            "batchId":       e.get("batch_id") or "",
            "promptVersion": e.get("prompt_version") or "",
            "ruleset":       "kyc-rules-v2.1",
            "eventHash":     event_hash,
            "prevHash":      prev_hash,
            "nextHash":      next_hash,
            "source":        "ui-app",
        })
    return {"logs": logs, "total": len(logs)}


def _action_group(action: str) -> str:
    if action in ("LOGIN", "LOGOUT"):
        return "auth"
    if action in ("APPROVE", "REJECT", "BATCH_RUN_COMPLETE", "CLEAR_APPROVED", "CLEAR_REJECTED",
                  "STATUS_CHANGE", "VIEW_CASE", "CASE_TAB_SWITCH"):
        return "case"
    if "RULESET" in action:
        return "ruleset"
    if action in ("FILE_UPLOAD", "EXPORT") or action.startswith("NAV_"):
        return "system"
    return "system"


def _format_audit_description(event: dict) -> str:
    details = event.get("details") or {}
    action  = event.get("action_type", "")
    user    = event.get("username", "")
    cid     = event.get("customer_id")
    desc    = details.get("description", "")
    if action == "LOGIN":
        return f"{user} authenticated"
    if action == "LOGOUT":
        return f"{user} logged out"
    if action == "BATCH_RUN_COMPLETE":
        return f"Batch complete — {details.get('total', 0)} customers, {details.get('flagged', 0)} flagged"
    if action == "FILE_UPLOAD":
        return f"Uploaded {details.get('filename', '')} ({details.get('rows', 0)} rows, type={details.get('dataset_type', '')})"
    if action == "STATUS_CHANGE":
        return desc or f"Status changed to {details.get('new_status', '?')} for {cid or 'unknown'}"
    if action == "VIEW_CASE":
        return desc or f"Viewed case {cid or '?'}"
    if action == "CASE_TAB_SWITCH":
        return desc or f"Switched to {details.get('tab', '?')} tab on case {cid or '?'}"
    if action.startswith("NAV_"):
        return desc or f"Navigated to {action[4:].lower()}"
    if action == "EXPORT":
        return desc or f"Exported {details.get('type', 'data')}"
    if desc:
        return desc
    if cid:
        return f"{action} on customer {cid}"
    return action

class AuditEventRequest(BaseModel):
    action: str
    description: str = ""
    customer_id: Optional[str] = None
    details: Dict[str, Any] = {}


@app.post("/api/audit/log")
def log_audit_event(payload: AuditEventRequest) -> Dict[str, str]:
    """Accept client-side UI events and append them to the session audit trail."""
    get_logger().log(
        payload.action,
        customer_id=payload.customer_id or None,
        details={"description": payload.description, **payload.details},
    )
    return {"ok": "true"}


@app.get("/api/system/info")
def system_info() -> Dict[str, Any]:
    import sys
    import platform
    import fastapi as _fa
    dfs = _load_temp_dfs()
    return {
        "python_version": sys.version.split()[0],
        "fastapi_version": _fa.__version__,
        "platform": platform.system(),
        "hostname": platform.node(),
        "active_sessions": len(SESSIONS),
        "datasets": {k: len(df) for k, df in dfs.items()},
    }


@app.get("/api/documents/preview/{filename:path}")
def document_preview(filename: str):
    """Serve raw bytes for a previously uploaded document (image or PDF)."""
    from fastapi.responses import Response
    entry = _DOC_VAULT.get(filename)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found in vault")
    raw, mime = entry
    return Response(content=raw, media_type=mime)


@app.get("/api/ai-observability")
def ai_observability() -> Dict[str, Any]:
    """Return real Claude + Google Vision usage metrics accumulated since server start."""
    return get_ai_tracker().get_summary()


@app.get("/api/ruleset")
def get_ruleset() -> Dict[str, Any]:
    """Return the active KYC ruleset JSON from the rules directory."""
    for fname in ("kyc_rules_v2.1.json", "kyc_rules_v2.0.json", "kyc_rules_v1.1.json", "kyc_rules_v1.0.json"):
        candidate = RULES_DIR / fname
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="No ruleset file found in rules/")


class RunBatchRequest(BaseModel):
    institution_id: Optional[str] = None


@app.post("/api/upload-docs")
async def upload_docs(
    files: List[UploadFile] = File(...),
    dataset_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Banker dashboard upload — no auth required."""
    results = []
    for f in files:
        raw = await f.read()
        result = process_file(raw, f.filename or "upload", dataset_type or "customers")
        results.append({
            "filename": result["filename"],
            "status": result["status"],
            "rows": result.get("rows", 0),
            "error": result.get("message", ""),
        })
    return {"ok": True, "results": results}


@app.post("/api/run-batch")
def run_batch(payload: RunBatchRequest) -> Dict[str, Any]:
    """Banker dashboard batch run — no auth required."""
    dfs = _load_temp_dfs()
    customers_df = dfs.get("customers", pd.DataFrame())

    if customers_df.empty:
        return {"ok": False, "error": "No data loaded. Use Batch upload to upload data first."}
    if "customer_id" not in customers_df.columns:
        return {"ok": False, "error": "customers dataset missing customer_id column"}

    filtered = customers_df.copy()
    if payload.institution_id:
        for col in ("institution_id", "institution"):
            if col in filtered.columns:
                filtered = filtered[filtered[col].astype(str) == payload.institution_id]
                break

    customer_ids = filtered["customer_id"].dropna().astype(str).unique().tolist()
    if not customer_ids:
        return {"ok": False, "error": "No customers found for the selected institution"}

    engine = KYCComplianceEngine(data_clean_dir=DATA_DIR)
    evaluations = []
    for cid in customer_ids:
        try:
            evaluations.append(engine.evaluate_customer(cid, institution_id=payload.institution_id))
        except Exception as ex:
            print(f"[RUN_BATCH] skip customer_id={cid!r}: {ex}")

    formatted = _format_results(evaluations, customers_df, dfs)
    for case in formatted.get("cases", []):
        cid = case.get("id")
        if not cid:
            continue
        override = APPROVALS.get(cid)
        if override == "approved":
            case["status"] = "Cleared"
            case["sla"] = {"tone": "ok", "label": "Approved"}
        elif override == "rejected":
            case["status"] = "Escalated"
            case["sla"] = {"tone": "bad", "label": "Rejected"}
    return {"ok": True, **formatted}


_DASHBOARD_DIR = Path(__file__).parent.parent / "atlas-kyc-dashboard"
app.mount("/", StaticFiles(directory=_DASHBOARD_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
