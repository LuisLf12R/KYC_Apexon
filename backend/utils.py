import io
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from kyc_dashboard.sidecar import _as_float, _safe

log = logging.getLogger(__name__)
_TEMP_DIR = Path(tempfile.gettempdir()) / "kyc_data_clean"


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


def _get_institutions():
    dfs = _load_temp_dfs()
    customers = dfs.get("customers", pd.DataFrame())
    result = []
    for col in ["institution_id", "institution"]:
        if col in customers.columns:
            for val in customers[col].dropna().unique():
                v = str(val).strip()
                if v:
                    result.append({"id": v, "label": v})
            break
    return result
