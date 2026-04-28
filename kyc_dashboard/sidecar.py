"""
kyc_dashboard/sidecar.py
Flask sidecar — runs as a daemon thread alongside Streamlit.
Provides JSON API endpoints that the Banker iframe calls via fetch().
Reads data from Path(tempfile.gettempdir()) / "kyc_data_clean" (written by save_to_temp()).
"""
from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

log = logging.getLogger(__name__)

_started = False
_lock    = threading.Lock()

_TEMP_DIR = Path(tempfile.gettempdir()) / "kyc_data_clean"

# ── Pure data helpers ──────────────────────────────────────────────────────────

def _safe(v: Any, default: str = "—") -> str:
    if v is None or (isinstance(v, float) and v != v):
        return default
    s = str(v).strip()
    return s if s else default


def _as_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _load_temp_dfs() -> Dict[str, pd.DataFrame]:
    name_map = {
        "customers_clean.csv":            "customers",
        "screenings_clean.csv":           "screenings",
        "id_verifications_clean.csv":     "id_verifications",
        "transactions_clean.csv":         "transactions",
        "documents_clean.csv":            "documents",
        "beneficial_ownership_clean.csv": "beneficial_ownership",
    }
    dfs: Dict[str, pd.DataFrame] = {}
    for fname, key in name_map.items():
        p = _TEMP_DIR / fname
        if p.exists():
            try:
                dfs[key] = pd.read_csv(p)
            except Exception as ex:
                log.warning("Could not load %s: %s", fname, ex)
    return dfs


def _format_results(
    results: List[Dict[str, Any]],
    customers_df: pd.DataFrame,
) -> Dict[str, Any]:
    """Convert raw engine result dicts to the React component data format."""
    cases: List[Dict[str, Any]] = []
    pass_count = review_count = fail_count = 0
    total_score = 0.0

    for r in results:
        cid   = str(r.get("customer_id", ""))
        score = int(round(_as_float(r.get("overall_score", 0))))
        disp  = str(r.get("disposition", "REVIEW")).upper()
        risk  = "low" if score >= 70 else "medium" if score >= 50 else "high"

        if disp == "PASS":
            pass_count += 1
            status = "Cleared"
            sla    = {"tone": "ok",   "label": "On track"}
        elif disp == "PASS_WITH_NOTES":
            review_count += 1
            status = "Dual-approval"
            sla    = {"tone": "warn", "label": "Pending sign-off"}
        elif disp == "REJECT":
            fail_count += 1
            status = "Escalated"
            sla    = {"tone": "bad",  "label": "Action needed"}
        else:
            review_count += 1
            status = "Pending review"
            sla    = {"tone": "warn", "label": "Under review"}

        total_score += score

        customer: Dict[str, Any] = {}
        if not customers_df.empty and "customer_id" in customers_df.columns:
            mask = customers_df["customer_id"].astype(str) == cid
            if mask.any():
                customer = customers_df[mask].iloc[0].to_dict()

        raw_name = ""
        for col in ["full_name", "customer_name", "name", "legal_name"]:
            v = customer.get(col)
            if v and str(v).strip():
                raw_name = str(v).strip()
                break
        display_name = raw_name or cid
        parts = display_name.upper().split()
        ini   = (parts[0][0] + parts[-1][0]) if len(parts) >= 2 else display_name[:2].upper()

        dim_fields = [
            ("identity",     "Identity verification", "identity_verification_score"),
            ("aml",          "AML / PEP screening",   "aml_screening_score"),
            ("ubo",          "Beneficial ownership",  "beneficial_ownership_score"),
            ("sow",          "Source of Wealth",      "source_of_wealth_score"),
            ("crs",          "CRS / FATCA",           "crs_fatca_score"),
            ("activity",     "Account activity",      "account_activity_score"),
            ("data_quality", "Data quality",          "data_quality_score"),
        ]
        dimensions = []
        for key, title, sf in dim_fields:
            s = int(round(_as_float(r.get(sf, 0))))
            if s > 0:
                tone = "ok" if s >= 70 else "warn" if s >= 50 else "bad"
                dimensions.append({
                    "key": key, "title": title, "score": s,
                    "tone": tone, "sub": f"Score: {s} / 100",
                })

        reject_rules: List[Dict[str, str]] = []
        review_rules: List[Dict[str, str]] = []
        for rule in r.get("triggered_reject_rules", []) or []:
            reject_rules.append({
                "name": _safe(rule.get("name") or rule.get("rule_id", ""))[:60],
                "desc": _safe(rule.get("description", ""))[:90],
            })
        for rule in r.get("triggered_review_rules", []) or []:
            review_rules.append({
                "name": _safe(rule.get("name") or rule.get("rule_id", ""))[:60],
                "desc": _safe(rule.get("description", ""))[:90],
            })

        cases.append({
            "id":          cid,
            "client":      display_name,
            "ini":         ini,
            "tier":        _safe(customer.get("risk_rating", "Standard")),
            "type":        _safe(customer.get("entity_type", "Individual")),
            "jurisdiction":_safe(customer.get("jurisdiction", "—")).upper(),
            "rm":          "Officer — J. Marlow",
            "status":      status,
            "risk":        risk,
            "riskScore":   score,
            "sla":         sla,
            "dimensions":  dimensions,
            "rejectRules": reject_rules,
            "reviewRules": review_rules,
            "rationale":   _safe(r.get("rationale", ""))[:200],
        })

    total = len(cases)
    avg   = int(round(total_score / total)) if total else 0

    return {
        "cases":   cases,
        "kpis": {
            "total":       total,
            "passCount":   pass_count,
            "passRate":    int(round(100 * pass_count / total)) if total else 0,
            "failCount":   fail_count,
            "reviewCount": review_count,
            "avgScore":    avg,
        },
        "batchId": datetime.now(timezone.utc).strftime("%H%M%S"),
        "runAt":   datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M UTC"),
    }


# ── OCR helpers (no Streamlit dependency) ─────────────────────────────────────

def _run_ocr(file_bytes: bytes, filename: str) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(io.BytesIO(file_bytes))
            if text and len(text.strip()) > 50:
                return text
        except Exception:
            pass
        try:
            import pdfplumber
            parts: List[str] = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        parts.append(t)
            text = "\n".join(parts)
            if text and len(text.strip()) > 50:
                return text
        except Exception:
            pass
        raise RuntimeError(
            "Could not extract text from PDF. "
            "Install: pip install pdfminer.six pdfplumber"
        )

    from google.cloud import vision as gv
    client = gv.ImageAnnotatorClient()
    resp   = client.document_text_detection(image=gv.Image(content=file_bytes))
    if resp.error.message:
        raise RuntimeError(f"Vision API error: {resp.error.message}")
    return resp.full_text_annotation.text if resp.full_text_annotation else ""


def _llm_structure(raw_text: str, dataset_type: str, filename: str) -> pd.DataFrame:
    import anthropic as ac

    client = ac.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    user_msg = (
        f"Dataset type: {dataset_type}\nFilename: {filename}\n\n"
        f"Extract all KYC records and return a JSON array. Text:\n{raw_text[:6000]}"
    )
    resp = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4000,
        system="Extract KYC records from the provided text and return a JSON array of records.",
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    records = json.loads(raw)
    if isinstance(records, dict):
        records = [records]
    return pd.DataFrame(records)


# ── Flask app factory ──────────────────────────────────────────────────────────

def _make_app():
    from flask import Flask, jsonify, request

    app = Flask(__name__)

    @app.after_request
    def _add_cors(response):
        response.headers["Access-Control-Allow-Origin"]  = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/run-batch", methods=["POST", "OPTIONS"])
    def run_batch():
        if request.method == "OPTIONS":
            return "", 204
        try:
            from kyc_engine.engine import KYCComplianceEngine

            payload        = request.get_json(silent=True) or {}
            institution_id = payload.get("institution_id") or None

            if not _TEMP_DIR.exists():
                return jsonify({
                    "ok": False,
                    "error": "No data loaded. Use the Data & Documents tab to upload data first.",
                }), 400

            engine    = KYCComplianceEngine(data_clean_dir=_TEMP_DIR)
            customers = engine.customers

            if customers is None or customers.empty:
                return jsonify({"ok": False, "error": "No customer records found."}), 400

            if institution_id:
                for col in ["institution_id", "institution"]:
                    if col in customers.columns:
                        customers = customers[customers[col].astype(str) == str(institution_id)]
                        break

            results: List[Dict[str, Any]] = []
            for _, row in customers.iterrows():
                cid = str(row.get("customer_id", ""))
                try:
                    r = engine.evaluate_customer(cid, institution_id=institution_id)
                    results.append(r)
                except Exception as ex:
                    log.warning("Skip customer %s: %s", cid, ex)

            component_data = _format_results(results, engine.customers)
            return jsonify({"ok": True, **component_data})

        except Exception as ex:
            log.exception("run-batch error")
            return jsonify({"ok": False, "error": str(ex)}), 500

    @app.route("/api/upload-docs", methods=["POST", "OPTIONS"])
    def upload_docs():
        if request.method == "OPTIONS":
            return "", 204
        try:
            files        = request.files.getlist("files")
            dataset_type = request.form.get("dataset_type", "customers")
            out: List[Dict[str, Any]] = []

            for f in files:
                fname = f.filename or "upload"
                try:
                    fbytes   = f.read()
                    raw_text = _run_ocr(fbytes, fname)
                    if not raw_text or len(raw_text.strip()) < 20:
                        raise ValueError("No usable text extracted from file.")
                    df = _llm_structure(raw_text, dataset_type, fname)

                    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
                    target = _TEMP_DIR / f"{dataset_type}_clean.csv"
                    if target.exists():
                        existing = pd.read_csv(target)
                        df = pd.concat([existing, df], ignore_index=True)
                    df.to_csv(target, index=False)

                    out.append({"filename": fname, "rows": len(df), "status": "ok"})
                except Exception as ex:
                    out.append({"filename": fname, "status": "error", "error": str(ex)})

            return jsonify({"ok": True, "results": out})

        except Exception as ex:
            log.exception("upload-docs error")
            return jsonify({"ok": False, "error": str(ex)}), 500

    return app


# ── Public entry point ─────────────────────────────────────────────────────────

def start_sidecar_thread(port: int = 8502) -> None:
    """Start the Flask sidecar in a background daemon thread (idempotent)."""
    global _started
    with _lock:
        if _started:
            return
        try:
            import flask  # noqa: F401
        except ImportError:
            log.warning(
                "Flask not installed — KYC sidecar disabled. "
                "Install with: pip install flask"
            )
            return
        app = _make_app()
        t = threading.Thread(
            target=lambda: app.run(
                host="127.0.0.1", port=port, debug=False, use_reloader=False
            ),
            daemon=True,
            name="kyc-sidecar",
        )
        t.start()
        _started = True
        log.info("KYC sidecar started on http://127.0.0.1:%d", port)
