from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.utils import _format_results, _get_institutions, _llm_structure, _load_temp_dfs, _run_ocr
from kyc_dashboard.banker_html import build_banker_html
from kyc_engine.engine import KYCComplianceEngine

DATA_DIR = Path(tempfile.gettempdir()) / "kyc_data_clean"


def _load_users() -> Dict[str, Dict[str, Any]]:
    """Load users from dashboard module with a minimal-role fallback."""
    try:
        from kyc_dashboard.main import load_users

        users = load_users()
        if isinstance(users, dict) and users:
            return users
    except Exception:
        pass

    # Fallback credentials aligned with dashboard defaults.
    return {
        "admin": {
            "user_id": "fb_admin",
            "username": "admin",
            "password": "admin123",
            "role": "Admin",
            "full_name": "Administrator",
        },
        "analyst1": {
            "user_id": "fb_a1",
            "username": "analyst1",
            "password": "analyst123",
            "role": "Analyst",
            "full_name": "KYC Analyst One",
        },
        "banker": {
            "user_id": "fb_banker",
            "username": "banker",
            "password": "banker123",
            "role": "Banker",
            "full_name": "Bank Operations User",
        },
    }


USERS = _load_users()
SESSIONS: Dict[str, Dict[str, Any]] = {}

app = FastAPI(title="KYC Backend API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def banker_dashboard() -> HTMLResponse:
    print("[DASHBOARD] render banker html")
    html = build_banker_html({"sidecarUrl": "http://127.0.0.1:8000"})
    return HTMLResponse(content=html, media_type="text/html")



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
    institution_id: str = Field(..., min_length=1)


class KYCBatchResponse(BaseModel):
    results: list[dict[str, Any]]
    summary: dict[str, int]


class KYCCustomerResponse(BaseModel):
    result: dict[str, Any]


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
        "role": user.get("role", "Analyst"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    print(f"[LOGIN] success username={payload.username!r} role={SESSIONS[token]['role']}")
    return LoginResponse(token=token, role=SESSIONS[token]["role"], message="Login successful")


@app.post("/api/auth/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest) -> MessageResponse:
    print("[LOGOUT] request")
    SESSIONS.pop(payload.token, None)
    return MessageResponse(message="Logged out")


@app.get("/api/health")
def health() -> Dict[str, str]:
    print("[HEALTH] check")
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/institutions")
def institutions(_: Dict[str, Any] = Depends(_require_session)) -> list[dict[str, str]]:
    print("[INSTITUTIONS] fetch")
    return _get_institutions()


@app.post("/api/kyc/batch", response_model=KYCBatchResponse)
def kyc_batch(
    payload: KYCBatchRequest,
    _: Dict[str, Any] = Depends(_require_session),
) -> KYCBatchResponse:
    print(f"[KYC_BATCH] institution_id={payload.institution_id!r}")
    dfs = _load_temp_dfs()
    customers_df = dfs.get("customers", pd.DataFrame())

    if customers_df.empty:
        raise HTTPException(status_code=404, detail="No customers dataset loaded")
    if "customer_id" not in customers_df.columns:
        raise HTTPException(status_code=500, detail="customers dataset missing customer_id")

    filtered_df = customers_df.copy()
    if "institution_id" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["institution_id"].astype(str) == payload.institution_id]
    elif "institution" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["institution"].astype(str) == payload.institution_id]
    else:
        raise HTTPException(
            status_code=400,
            detail="customers dataset has no institution_id/institution column",
        )

    customer_ids = filtered_df["customer_id"].dropna().astype(str).unique().tolist()
    if not customer_ids:
        return KYCBatchResponse(results=[], summary={"total": 0, "flagged": 0})

    engine = KYCComplianceEngine(data_clean_dir=DATA_DIR)
    evaluations = []
    for cid in customer_ids:
        try:
            evaluations.append(engine.evaluate_customer(cid, institution_id=payload.institution_id))
        except Exception as ex:
            print(f"[KYC_BATCH] evaluation error customer_id={cid!r}: {ex}")

    formatted = _format_results(evaluations, customers_df)
    flagged = sum(1 for r in evaluations if str(r.get("disposition", "")).upper() != "PASS")
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
    formatted = _format_results([result], customers_df)
    cases = formatted.get("cases", [])
    if not cases:
        raise HTTPException(status_code=500, detail="Unable to format customer result")

    return KYCCustomerResponse(result=cases[0])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
