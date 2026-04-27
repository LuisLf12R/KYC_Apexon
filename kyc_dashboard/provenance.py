"""
Data provenance system for the KYC dashboard.

Tracks field-level attribution: which value came from which source file,
at what confidence, via which extraction method (User-Provided vs OCR-Extracted).
Detects discrepancies when the same field has conflicting values from different sources.

Ported from legacy dashboard provenance patterns (Phase 11B).
"""

import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class ProvenanceRecord:
    """Single field-value attribution record."""

    customer_id: str
    field_name: str
    value: Any
    source_type: str
    source_file: str
    confidence: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())

    @property
    def source(self) -> str:
        """Compatibility alias for legacy provenance consumers."""
        return self.source_type


@dataclass
class Discrepancy:
    """A field where two sources disagree on the value."""

    customer_id: str
    field_name: str
    existing_value: Any
    existing_source: str
    new_value: Any
    new_source: str


class ProvenanceStore:
    """
    In-memory provenance store keyed by "customer_id::field_name".
    Multiple records per key are retained.
    """

    def __init__(self):
        self._records: Dict[str, List[ProvenanceRecord]] = {}

    def _key(self, customer_id: str, field_name: str) -> str:
        return str(customer_id) + "::" + str(field_name)

    def add_record(self, record: ProvenanceRecord) -> None:
        key = self._key(record.customer_id, record.field_name)
        if key not in self._records:
            self._records[key] = []
        self._records[key].append(record)

    def get_records(self, customer_id: str, field_name: Optional[str] = None) -> List[ProvenanceRecord]:
        if field_name is not None:
            key = self._key(customer_id, field_name)
            return list(self._records.get(key, []))
        prefix = str(customer_id) + "::"
        result: List[ProvenanceRecord] = []
        for key, records in self._records.items():
            if key.startswith(prefix):
                result.extend(records)
        return result

    def get_all_customers(self) -> List[str]:
        seen = set()
        for key in self._records:
            seen.add(key.split("::", 1)[0])
        return sorted(seen)

    def clear(self) -> None:
        self._records.clear()

    # ── Legacy compatibility helpers (used by main.py tab code) ────────────
    def set_field(
        self,
        customer_id: str,
        field_name: str,
        value: Any,
        *,
        source: str = "User-Provided",
        source_file: str = "",
        confidence: Optional[float] = None,
    ) -> ProvenanceRecord:
        rec = ProvenanceRecord(
            customer_id=str(customer_id),
            field_name=str(field_name),
            value=value,
            source_type=source,
            source_file=source_file,
            confidence=_normalize_confidence(confidence),
        )
        self.add_record(rec)
        return rec

    def get_field_history(self, customer_id: str, field_name: str) -> List[ProvenanceRecord]:
        return self.get_records(str(customer_id), str(field_name))

    def get_customer_ids(self) -> List[str]:
        return self.get_all_customers()

    def get_all_fields(self, customer_id: str) -> Dict[str, ProvenanceRecord]:
        latest_by_field: Dict[str, ProvenanceRecord] = {}
        for rec in self.get_records(str(customer_id)):
            prev = latest_by_field.get(rec.field_name)
            if prev is None or str(rec.timestamp) >= str(prev.timestamp):
                latest_by_field[rec.field_name] = rec
        return latest_by_field

    def detect_discrepancies(self, customer_id: str) -> List[Dict[str, Any]]:
        by_field: Dict[str, List[ProvenanceRecord]] = {}
        for rec in self.get_records(str(customer_id)):
            by_field.setdefault(rec.field_name, []).append(rec)

        discrepancies: List[Dict[str, Any]] = []
        for field_name, recs in by_field.items():
            values_by_source: Dict[str, Dict[str, Any]] = {}
            unique_values = set()
            for rec in recs:
                src = rec.source_type or "Unknown"
                values_by_source[src] = {
                    "value": rec.value,
                    "source_file": rec.source_file,
                    "confidence": rec.confidence,
                    "timestamp": rec.timestamp,
                }
                unique_values.add(str(rec.value).strip().lower() if rec.value is not None else "")
            if len(unique_values) > 1 and len(values_by_source) > 1:
                discrepancies.append(
                    {
                        "field_name": field_name,
                        "values_by_source": values_by_source,
                    }
                )
        return discrepancies

    def get_customer_history_rows(self, customer_id: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for rec in sorted(self.get_records(str(customer_id)), key=lambda r: str(r.timestamp)):
            rows.append(
                {
                    "Timestamp": rec.timestamp,
                    "Field": rec.field_name,
                    "Value": rec.value,
                    "Source": rec.source_type,
                    "Source File": rec.source_file,
                    "Confidence": rec.confidence,
                }
            )
        return rows


def _normalize_confidence(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    conf = float(value)
    if conf > 1.0:
        conf = conf / 100.0
    if conf < 0.0:
        conf = 0.0
    if conf > 1.0:
        conf = 1.0
    return conf


def record_ocr_provenance(
    store: ProvenanceStore,
    customer_id: str,
    extracted_fields: Dict[str, Any],
    source_file: str,
    confidences: Optional[Dict[str, float]] = None,
) -> List[ProvenanceRecord]:
    """Record OCR-extracted fields into the provenance store."""
    created: List[ProvenanceRecord] = []
    for field_name, value in extracted_fields.items():
        conf = None
        if confidences is not None and field_name in confidences:
            conf = _normalize_confidence(confidences[field_name])
        rec = ProvenanceRecord(
            customer_id=str(customer_id),
            field_name=field_name,
            value=value,
            source_type="OCR-Extracted",
            source_file=source_file,
            confidence=conf,
        )
        store.add_record(rec)
        created.append(rec)
    return created


def collect_discrepancies(store: ProvenanceStore, customer_id: str) -> List[Discrepancy]:
    """Find conflicting values for the same field across provenance sources."""
    records = store.get_records(str(customer_id))
    by_field: Dict[str, List[ProvenanceRecord]] = {}
    for rec in records:
        if rec.field_name not in by_field:
            by_field[rec.field_name] = []
        by_field[rec.field_name].append(rec)

    discrepancies: List[Discrepancy] = []
    for field_name, recs in by_field.items():
        if len(recs) < 2:
            continue
        unique_values: Dict[str, ProvenanceRecord] = {}
        for rec in recs:
            value_key = ""
            if rec.value is not None:
                value_key = str(rec.value).strip().lower()
            if value_key not in unique_values:
                unique_values[value_key] = rec
        if len(unique_values) > 1:
            values = list(unique_values.values())
            discrepancies.append(
                Discrepancy(
                    customer_id=str(customer_id),
                    field_name=field_name,
                    existing_value=values[0].value,
                    existing_source=values[0].source_file + " (" + values[0].source_type + ")",
                    new_value=values[1].value,
                    new_source=values[1].source_file + " (" + values[1].source_type + ")",
                )
            )
    return discrepancies


def _upsert_customer_row(df: pd.DataFrame, customer_id: str, values: Dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    if "customer_id" not in out.columns:
        out["customer_id"] = None
    for col in values:
        if col not in out.columns:
            out[col] = None

    match_idx = out.index[out["customer_id"].astype(str) == str(customer_id)].tolist()
    if match_idx:
        idx = match_idx[0]
        for col, val in values.items():
            if val is not None and str(val).strip() != "":
                    # BF-27: CSV round-trip can leave columns as float64 when they
                    # originally held mixed or string data. If assigning a non-numeric
                    # value into a numeric column, convert the column to object first.
                    if col in out.columns:
                        if out[col].dtype.kind in ("f", "i", "u") and isinstance(val, str):
                            out[col] = out[col].astype(object)
                    out.at[idx, col] = val
    else:
        row = {"customer_id": str(customer_id)}
        for col, val in values.items():
            if val is not None and str(val).strip() != "":
                row[col] = val
        out = pd.concat([out, pd.DataFrame([row])], ignore_index=True)
    return out


def update_customer_records(
    dataframes: Dict[str, pd.DataFrame],
    customer_id: str,
    document_type: str,
    extracted_fields: Dict[str, Any],
) -> Dict[str, pd.DataFrame]:
    """Upsert extracted document data into routed DataFrames and return copies."""
    result = {k: v.copy() for k, v in dataframes.items()}

    normalized_doc_type = str(document_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    now_date = datetime.datetime.utcnow().date().isoformat()

    id_doc_types = {"drivers_license", "passport", "national_id"}
    poa_doc_types = {"utility_bill", "bank_statement", "credit_report"}

    id_values = {
        "document_type": normalized_doc_type or extracted_fields.get("document_type"),
        "document_number": extracted_fields.get("document_number"),
        "issue_date": extracted_fields.get("issue_date"),
        "expiry_date": extracted_fields.get("expiry_date"),
        "verification_date": extracted_fields.get("verification_date") or now_date,
        "document_status": extracted_fields.get("document_status") or "VERIFIED",
    }
    poa_values = {
        "document_type": normalized_doc_type or extracted_fields.get("document_type"),
        "issue_date": extracted_fields.get("issue_date"),
        "expiry_date": extracted_fields.get("expiry_date"),
        "document_category": extracted_fields.get("document_category") or "POA",
    }

    if normalized_doc_type in id_doc_types:
        base = result.get("id_verifications", pd.DataFrame())
        result["id_verifications"] = _upsert_customer_row(base, str(customer_id), id_values)
    elif normalized_doc_type in poa_doc_types:
        base = result.get("documents", pd.DataFrame())
        result["documents"] = _upsert_customer_row(base, str(customer_id), poa_values)

    return result


def get_provenance_store() -> ProvenanceStore:
    """Get or create the ProvenanceStore in Streamlit session state."""
    import streamlit as st

    existing = st.session_state.get("provenance_store", None)
    if existing is None or not isinstance(existing, ProvenanceStore):
        st.session_state["provenance_store"] = ProvenanceStore()
    return st.session_state["provenance_store"]
