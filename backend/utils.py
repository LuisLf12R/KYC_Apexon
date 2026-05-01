import io
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

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
    
    # Load known files first
    for fname, key in name_map.items():
        p = _TEMP_DIR / fname
        if p.exists():
            try:
                dfs[key] = pd.read_csv(p)
            except Exception as ex:
                log.warning("Could not load %s: %s", fname, ex)
    
    # Scan for additional *_clean.csv files not in the fixed list
    for p in _TEMP_DIR.glob("*_clean.csv"):
        if p.name not in name_map:
            try:
                # Extract dataset type from filename stem
                key = p.stem.replace("_clean", "")
                dfs[key] = pd.read_csv(p)
                log.info("Loaded additional dataset from %s as %s", p.name, key)
            except Exception as ex:
                log.warning("Could not load additional file %s: %s", p.name, ex)
    
    # Fallback: If no customers dataset found, look for any dataset with customer_id column
    if "customers" not in dfs:
        for key, df in dfs.items():
            if "customer_id" in df.columns:
                dfs["customers"] = df
                log.info("Promoted %s dataset as customers (found customer_id column)", key)
                break
    
    return dfs


def _df_rows_for(df: pd.DataFrame, cid: str) -> List[Dict[str, Any]]:
    """Return all rows matching customer_id as plain dicts."""
    if df is None or df.empty or "customer_id" not in df.columns:
        return []
    mask = df["customer_id"].astype(str) == cid
    return [
        {k: ("" if (v != v or v is None) else str(v)) for k, v in row.items()}
        for row in df[mask].to_dict("records")
    ]


def _format_results(
    results: List[Dict[str, Any]],
    customers_df: pd.DataFrame,
    dfs: Optional[Dict[str, pd.DataFrame]] = None,
) -> Dict[str, Any]:
    """Convert raw engine result dicts to the React component data format."""
    dfs = dfs or {}
    docs_df  = dfs.get("documents",            pd.DataFrame())
    ubo_df   = dfs.get("beneficial_ownership", pd.DataFrame())
    idv_df   = dfs.get("id_verifications",     pd.DataFrame())
    scr_df   = dfs.get("screenings",           pd.DataFrame())

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
            if v and str(v).strip() and str(v).strip().lower() != "nan":
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

        jur   = _safe(customer.get("jurisdiction", "—")).upper()
        flags = [rule["name"] for rule in (reject_rules + review_rules)] or ["No compliance flags"]
        aum_raw = _as_float(customer.get("aum") or customer.get("assets_under_management") or 0)
        aum_str = f"{aum_raw:.1f}" if aum_raw else "N/A"

        # ── Real documents from documents_clean.csv ──────────────────────────
        raw_docs = _df_rows_for(docs_df, cid)
        documents = [
            {
                "name":      d.get("document_reference") or d.get("document_type", "Document"),
                "type":      d.get("document_type", "").replace("_", " ").title(),
                "status":    d.get("document_status", "Unknown"),
                "issueDate": d.get("issue_date", ""),
                "expiry":    d.get("expiry_date", ""),
                "issuer":    d.get("issuing_entity", ""),
            }
            for d in raw_docs
        ]

        # ── Real UBO data from beneficial_ownership_clean.csv ─────────────────
        raw_ubos = _df_rows_for(ubo_df, cid)
        ubos = [
            {
                "name":       u.get("ubo_name", "Unknown"),
                "pct":        u.get("ownership_percentage", ""),
                "country":    u.get("country_of_residence", ""),
                "isPep":      str(u.get("is_pep", "False")).lower() in ("true", "1", "yes"),
                "verified":   u.get("verification_date", ""),
            }
            for u in raw_ubos
        ]

        # ── Real ID verification ──────────────────────────────────────────────
        raw_idv = _df_rows_for(idv_df, cid)
        id_verifications = [
            {
                "docType":    v.get("document_type", ""),
                "docNumber":  v.get("document_number", ""),
                "country":    v.get("issuing_country", ""),
                "expiry":     v.get("expiry_date", ""),
                "status":     v.get("verification_status", ""),
                "date":       v.get("verification_date", ""),
            }
            for v in raw_idv
        ]

        # ── Real screening results ────────────────────────────────────────────
        raw_scr = _df_rows_for(scr_df, cid)
        screenings = [
            {
                "date":       s.get("screening_date", ""),
                "result":     s.get("screening_result", ""),
                "resolution": s.get("resolution_status", ""),
                "matchedName":s.get("matched_name", ""),
                "list":       s.get("matched_list", ""),
                "score":      s.get("match_score", ""),
            }
            for s in raw_scr
        ]

        cases.append({
            "id":               cid,
            "client":           display_name,
            "ini":              ini,
            "tier":             _safe(customer.get("risk_rating", "Standard")),
            "type":             _safe(customer.get("entity_type", "Individual")).capitalize(),
            "jurisdiction":     jur,
            "jurisdictions":    [jur],
            "countryOfOrigin":  _safe(customer.get("country_of_origin", jur)),
            "dateOfBirth":      _safe(customer.get("date_of_birth", "")),
            "accountOpenDate":  _safe(customer.get("account_open_date", "")),
            "lastKycReview":    _safe(customer.get("last_kyc_review_date", "")),
            "rm":               "Compliance Officer",
            "status":           status,
            "risk":             risk,
            "riskScore":        score,
            "aum":              aum_str,
            "sla":              sla,
            "flags":            flags,
            "dimensions":       dimensions,
            "rejectRules":      reject_rules,
            "reviewRules":      review_rules,
            "rationale":        _safe(r.get("rationale", ""))[:300],
            "documents":        documents,
            "ubos":             ubos,
            "idVerifications":  id_verifications,
            "screenings":       screenings,
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
