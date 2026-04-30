"""
backend/pipeline.py
File processing pipeline: upload → OCR/LLM → canonical CSV.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

log = logging.getLogger(__name__)

TEMP_DIR = Path(tempfile.gettempdir()) / "kyc_data_clean"

# Maps dataset type → output filename
DATASET_FILES: Dict[str, str] = {
    "customers":           "customers_clean.csv",
    "screenings":          "screenings_clean.csv",
    "id_verifications":    "id_verifications_clean.csv",
    "transactions":        "transactions_clean.csv",
    "documents":           "documents_clean.csv",
    "beneficial_ownership":"beneficial_ownership_clean.csv",
}

# Column aliases → canonical name
COLUMN_ALIASES: Dict[str, str] = {
    "id": "customer_id", "cust_id": "customer_id", "client_id": "customer_id",
    "name": "full_name", "customer_name": "full_name", "legal_name": "full_name",
    "dob": "date_of_birth", "birth_date": "date_of_birth",
    "nationality": "jurisdiction", "country": "jurisdiction",
    "institution": "institution_id",
    "screen_id": "screening_id", "screening_result": "result",
    "doc_id": "document_id", "doc_type": "document_type",
    "txn_id": "transaction_id", "tx_id": "transaction_id",
    "amount": "transaction_amount", "value": "transaction_amount",
}


def _harmonize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase + strip all column names, apply known aliases."""
    df.columns = [c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]
    df.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in df.columns}, inplace=True)
    return df


def _detect_dataset_type(df: pd.DataFrame, filename: str) -> str:
    """Heuristic dataset type detection from column names and filename."""
    cols = set(df.columns)
    fname = filename.lower()
    
    # Phase 1: Filename-based detection (highest priority)
    # Check for explicit dataset type keywords in filename first
    if "customer" in fname:
        return "customers"
    if "screen" in fname and "screening" not in fname:
        # If filename has "screen" but not "screening", likely a transaction
        return "screenings"  
    if "screening" in fname:
        return "screenings"
    if "transaction" in fname or "txn" in fname:
        return "transactions"
    if "document" in fname or "proof" in fname:
        return "documents"
    if "beneficial" in fname or "ubo" in fname or "ownership" in fname:
        return "beneficial_ownership"
    if "verification" in fname or "id_ver" in fname or "id_verification" in fname:
        return "id_verifications"
    
    # Phase 2: Column-based fingerprinting (fallback)
    if cols & {"screening_id", "hit_count", "pep_flag"}:
        return "screenings"
    if cols & {"transaction_id", "transaction_amount"}:
        return "transactions"
    if cols & {"document_id", "document_type", "expiry_date"}:
        return "documents"
    if cols & {"beneficial_owner", "ownership_pct"}:
        return "beneficial_ownership"
    if cols & {"verification_id", "id_number"}:
        return "id_verifications"
    
    # Phase 3: Default fallback
    return "customers"


def _run_ocr(file_bytes: bytes, filename: str) -> str:
    """Extract text from image/PDF. Uses Google Vision for images, pdfminer for PDFs."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        for extractor in (_pdf_pdfminer, _pdf_pdfplumber):
            try:
                text = extractor(file_bytes)
                if text and len(text.strip()) > 50:
                    return text
            except Exception:
                pass
        raise RuntimeError("Could not extract text from PDF — install pdfminer.six or pdfplumber")

    from google.cloud import vision as gv
    client = gv.ImageAnnotatorClient()
    resp = client.document_text_detection(image=gv.Image(content=file_bytes))
    if resp.error.message:
        raise RuntimeError(f"Vision API error: {resp.error.message}")
    return resp.full_text_annotation.text if resp.full_text_annotation else ""


def _pdf_pdfminer(data: bytes) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(io.BytesIO(data))


def _pdf_pdfplumber(data: bytes) -> str:
    import pdfplumber
    parts: List[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                parts.append(t)
    return "\n".join(parts)


def _llm_structure(raw_text: str, dataset_type: str, filename: str) -> pd.DataFrame:
    """Ask Claude to turn OCR text into a JSON array of KYC records."""
    import anthropic as ac
    client = ac.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    system = (
        "You are a KYC data extraction assistant. "
        "Extract structured records from the provided text and return ONLY a JSON array. "
        "No explanation, no markdown fences — just the raw JSON array."
    )
    user = (
        f"Dataset type: {dataset_type}\nFilename: {filename}\n\n"
        f"Extract all records and return as a JSON array:\n{raw_text[:8000]}"
    )
    resp = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw).strip()
    try:
        records = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON response: {exc}") from exc
    if isinstance(records, dict):
        records = [records]
    return pd.DataFrame(records)


def _read_structured(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read CSV / Excel / JSON directly into a DataFrame."""
    ext = Path(filename).suffix.lower()
    buf = io.BytesIO(file_bytes)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(buf)
    if ext in (".json", ".jsonl"):
        try:
            return pd.read_json(buf, lines=(ext == ".jsonl"))
        except Exception:
            data = json.loads(file_bytes.decode("utf-8", errors="replace"))
            if isinstance(data, dict):
                data = [data]
            return pd.DataFrame(data)
    return pd.read_csv(buf, on_bad_lines="skip")


def _save(df: pd.DataFrame, dataset_type: str) -> Path:
    """Append-or-create clean CSV in TEMP_DIR."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    fname = DATASET_FILES.get(dataset_type, f"{dataset_type}_clean.csv")
    dest = TEMP_DIR / fname
    if dest.exists():
        existing = pd.read_csv(dest)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates()
    df.to_csv(dest, index=False)
    return dest


def process_file(
    file_bytes: bytes,
    filename: str,
    dataset_type: str | None = None,
) -> Dict[str, Any]:
    """
    Full pipeline for one file. Returns a result dict with keys:
      filename, dataset_type, rows, status, message
    """
    ext = Path(filename).suffix.lower()
    structured_exts = {".csv", ".xlsx", ".xls", ".json", ".jsonl"}
    unstructured_exts = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

    try:
        if ext in structured_exts:
            df = _read_structured(file_bytes, filename)
            df = _harmonize_columns(df)
            resolved_type = dataset_type or _detect_dataset_type(df, filename)
        elif ext in unstructured_exts:
            raw_text = _run_ocr(file_bytes, filename)
            resolved_type = dataset_type or "customers"
            df = _llm_structure(raw_text, resolved_type, filename)
            df = _harmonize_columns(df)
        else:
            return {
                "filename": filename, "dataset_type": None,
                "rows": 0, "status": "rejected",
                "message": f"Unsupported file type: {ext}",
            }

        dest = _save(df, resolved_type)
        return {
            "filename": filename,
            "dataset_type": resolved_type,
            "rows": len(df),
            "status": "ok",
            "message": f"Saved {len(df)} rows → {dest.name}",
        }
    except Exception as exc:
        log.exception("Pipeline error for %s", filename)
        return {
            "filename": filename,
            "dataset_type": dataset_type,
            "rows": 0,
            "status": "error",
            "message": str(exc),
        }
