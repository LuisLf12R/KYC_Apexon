"""
backend/ai_observability.py
In-process tracker for Claude and Google Vision API usage.
Populated by pipeline.py on every OCR/LLM call; read by /api/ai-observability.
Resets on server restart — this is intentional for demo/session scoping.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional

# Claude claude-opus-4 pricing (per token, USD)
_CLAUDE_INPUT_COST_PER_TOKEN  = 15.0  / 1_000_000   # $15/MTok
_CLAUDE_OUTPUT_COST_PER_TOKEN = 75.0  / 1_000_000   # $75/MTok

# Google Vision DOCUMENT_TEXT_DETECTION pricing
_VISION_COST_PER_IMAGE = 1.50 / 1_000               # $1.50/1K images


@dataclass
class _UsageRecord:
    timestamp: float
    service: str          # "claude" | "vision"
    model: str
    input_tokens: int  = 0
    output_tokens: int = 0
    latency_ms: float  = 0.0
    cost_usd: float    = 0.0
    doc_type: str      = ""   # filename or document hint


class AIObservabilityTracker:
    def __init__(self) -> None:
        self._records: List[_UsageRecord] = []
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Write side — called from pipeline.py
    # ------------------------------------------------------------------

    def track_claude(
        self,
        model: str,
        usage: Any,
        latency_ms: float,
        doc_type: str = "",
    ) -> None:
        inp  = getattr(usage, "input_tokens",  0) or 0
        out  = getattr(usage, "output_tokens", 0) or 0
        cost = inp * _CLAUDE_INPUT_COST_PER_TOKEN + out * _CLAUDE_OUTPUT_COST_PER_TOKEN
        with self._lock:
            self._records.append(_UsageRecord(
                timestamp  = time.time(),
                service    = "claude",
                model      = model,
                input_tokens  = inp,
                output_tokens = out,
                latency_ms    = latency_ms,
                cost_usd      = cost,
                doc_type      = doc_type,
            ))

    def track_vision(self, latency_ms: float, doc_type: str = "") -> None:
        with self._lock:
            self._records.append(_UsageRecord(
                timestamp  = time.time(),
                service    = "vision",
                model      = "google-vision-document-text-detection",
                latency_ms = latency_ms,
                cost_usd   = _VISION_COST_PER_IMAGE,
                doc_type   = doc_type,
            ))

    # ------------------------------------------------------------------
    # Read side — called from /api/ai-observability
    # ------------------------------------------------------------------

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._records)

        if not records:
            return {
                "has_data": False,
                "total_calls": 0,
                "message": "No AI calls recorded yet. Upload an image or PDF document to populate real metrics.",
            }

        claude_recs  = [r for r in records if r.service == "claude"]
        vision_recs  = [r for r in records if r.service == "vision"]

        total_input   = sum(r.input_tokens  for r in claude_recs)
        total_output  = sum(r.output_tokens for r in claude_recs)
        claude_cost   = sum(r.cost_usd for r in claude_recs)
        vision_cost   = sum(r.cost_usd for r in vision_recs)
        total_cost    = claude_cost + vision_cost

        docs_processed = len(vision_recs) if vision_recs else len(claude_recs)

        claude_lat = sorted(r.latency_ms for r in claude_recs if r.latency_ms > 0)
        vision_lat = sorted(r.latency_ms for r in vision_recs if r.latency_ms > 0)

        def _p95(vals: list) -> float:
            if not vals:
                return 0.0
            idx = max(0, int(len(vals) * 0.95) - 1)
            return round(vals[idx], 1)

        def _avg(vals: list) -> float:
            return round(sum(vals) / len(vals), 1) if vals else 0.0

        cost_per_doc = round(total_cost / docs_processed, 4) if docs_processed else 0.0

        return {
            "has_data": True,
            "total_calls": len(records),
            "docs_processed": docs_processed,
            "cost_per_doc_usd": cost_per_doc,
            "total_cost_usd": round(total_cost, 4),
            "claude": {
                "calls":          len(claude_recs),
                "input_tokens":   total_input,
                "output_tokens":  total_output,
                "total_tokens":   total_input + total_output,
                "cost_usd":       round(claude_cost, 4),
                "avg_latency_ms": _avg(claude_lat),
                "p95_latency_ms": _p95(claude_lat),
                "model":          claude_recs[0].model if claude_recs else "claude-opus-4",
            },
            "vision": {
                "calls":          len(vision_recs),
                "cost_usd":       round(vision_cost, 4),
                "avg_latency_ms": _avg(vision_lat),
                "p95_latency_ms": _p95(vision_lat),
            },
        }


# Module-level singleton — survives within a server process
_tracker = AIObservabilityTracker()


def get_tracker() -> AIObservabilityTracker:
    return _tracker
