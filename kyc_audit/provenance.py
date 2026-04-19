"""
data_provenance.py
------------------
Field-level provenance tracking for KYC customer data.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


VALID_SOURCES = {
    "User-Provided",
    "OCR-Extracted",
    "LLM-Inferred",
    "System-Generated",
}


@dataclass
class ProvenanceTag:
    value: Any
    source: str
    source_file: Optional[str]
    confidence: Optional[float]
    timestamp: str
    field_name: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CustomerProvenance:
    """
    Structure:
      { customer_id: { field_name: [ProvenanceTag, ...] } }
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, List[ProvenanceTag]]] = {}

    def set_field(
        self,
        customer_id: str,
        field_name: str,
        value: Any,
        source: str,
        source_file: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> ProvenanceTag:
        if source not in VALID_SOURCES:
            source = "System-Generated"
        if confidence is not None:
            confidence = max(0.0, min(1.0, float(confidence)))
        tag = ProvenanceTag(
            value=value,
            source=source,
            source_file=source_file,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            field_name=field_name,
        )
        cid = str(customer_id)
        self._store.setdefault(cid, {})
        self._store[cid].setdefault(field_name, [])
        self._store[cid][field_name].append(tag)
        return tag

    def get_field_history(self, customer_id: str, field_name: str) -> List[ProvenanceTag]:
        cid = str(customer_id)
        return list(self._store.get(cid, {}).get(field_name, []))

    def get_latest(self, customer_id: str, field_name: str) -> Optional[ProvenanceTag]:
        history = self.get_field_history(customer_id, field_name)
        return history[-1] if history else None

    def get_all_fields(self, customer_id: str) -> Dict[str, ProvenanceTag]:
        cid = str(customer_id)
        out: Dict[str, ProvenanceTag] = {}
        for field_name, tags in self._store.get(cid, {}).items():
            if tags:
                out[field_name] = tags[-1]
        return out

    def get_customer_ids(self) -> List[str]:
        return sorted(self._store.keys())

    def get_customer_history_rows(self, customer_id: str) -> List[Dict[str, Any]]:
        cid = str(customer_id)
        rows: List[Dict[str, Any]] = []
        for field_name, tags in self._store.get(cid, {}).items():
            for tag in tags:
                rows.append(
                    {
                        "Customer ID": cid,
                        "Field": field_name,
                        "Value": tag.value,
                        "Source": tag.source,
                        "Source File": tag.source_file or "",
                        "Confidence": tag.confidence,
                        "Timestamp": tag.timestamp,
                    }
                )
        rows.sort(key=lambda r: r["Timestamp"])
        return rows

    def detect_discrepancies(self, customer_id: str) -> List[dict]:
        cid = str(customer_id)
        discrepancies: List[dict] = []
        fields = self._store.get(cid, {})
        for field_name, tags in fields.items():
            if len(tags) < 2:
                continue
            # Compare normalized values by source
            value_by_source: Dict[str, Dict[str, Any]] = {}
            for tag in tags:
                val_norm = str(tag.value).strip().lower()
                if val_norm in ("", "none", "nan"):
                    continue
                value_by_source.setdefault(tag.source, {
                    "value": tag.value,
                    "source_file": tag.source_file,
                    "confidence": tag.confidence,
                    "timestamp": tag.timestamp,
                })
            distinct_values = {str(v["value"]).strip().lower() for v in value_by_source.values()}
            if len(distinct_values) > 1 and len(value_by_source) > 1:
                discrepancies.append(
                    {
                        "customer_id": cid,
                        "field_name": field_name,
                        "values_by_source": value_by_source,
                    }
                )
        return discrepancies
