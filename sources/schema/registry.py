"""
Pydantic v2 schema for sources/registry.yaml.

Models
------
FetchMethod     — enum of valid fetch strategies per URL
ParseMode       — enum of valid extraction strategies per source
UrlEntry        — a single URL within a source (label, url, fetch_method)
RegistryEntry   — one regulatory source (id, urls, parse_mode, active, ...)
RegistryManifest — top-level wrapper (schema_version + sources list)

Validators
----------
- UrlEntry: url must start with http:// or https://
- RegistryEntry: urls list must not be empty
- RegistryEntry: url labels must be unique within the source
- RegistryEntry: api_status sources must have parse_mode=none; others must not
- RegistryManifest: source ids must be unique across the manifest

load_registry(path) — loads and validates registry.yaml from a given path
"""

from __future__ import annotations

import os
from enum import Enum
from typing import List, Optional

import yaml
from pydantic import BaseModel, field_validator, model_validator


class FetchMethod(str, Enum):
    http_head = "http_head"
    http_get = "http_get"
    playwright = "playwright"
    rss = "rss"
    api_status = "api_status"


class ParseMode(str, Enum):
    llm = "llm"
    direct = "direct"
    none = "none"


class UrlEntry(BaseModel):
    label: str
    url: str
    fetch_method: FetchMethod

    @field_validator("url")
    @classmethod
    def url_must_have_scheme(cls, v: str) -> str:
        if not v.startswith("http://") and not v.startswith("https://"):
            raise ValueError(f"url must start with http:// or https://, got: {v!r}")
        return v


class RegistryEntry(BaseModel):
    id: str
    jurisdiction: str
    regulator: str
    document_name: str
    urls: List[UrlEntry]
    parse_mode: ParseMode
    relevant_sections: str
    active: bool
    notes: Optional[str] = None

    @field_validator("urls")
    @classmethod
    def urls_not_empty(cls, v: List[UrlEntry]) -> List[UrlEntry]:
        if not v:
            raise ValueError("urls must contain at least one entry")
        return v

    @model_validator(mode="after")
    def validate_url_labels_unique(self) -> "RegistryEntry":
        labels = [u.label for u in self.urls]
        if len(labels) != len(set(labels)):
            dupes = [l for l in labels if labels.count(l) > 1]
            raise ValueError(
                f"Source {self.id!r}: duplicate url labels: {list(set(dupes))}"
            )
        return self

    @model_validator(mode="after")
    def validate_parse_mode_vs_fetch_method(self) -> "RegistryEntry":
        all_api_status = all(
            u.fetch_method == FetchMethod.api_status for u in self.urls
        )
        if all_api_status and self.parse_mode != ParseMode.none:
            raise ValueError(
                f"Source {self.id!r}: all URLs are api_status "
                f"but parse_mode={self.parse_mode.value!r} — expected 'none'"
            )
        if not all_api_status and self.parse_mode == ParseMode.none:
            raise ValueError(
                f"Source {self.id!r}: parse_mode='none' but not all URLs "
                f"use fetch_method=api_status"
            )
        return self


class RegistryManifest(BaseModel):
    schema_version: str
    sources: List[RegistryEntry]

    @model_validator(mode="after")
    def validate_source_ids_unique(self) -> "RegistryManifest":
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            dupes = [i for i in ids if ids.count(i) > 1]
            raise ValueError(
                f"Duplicate source ids in registry: {list(set(dupes))}"
            )
        return self


def load_registry(path: str | os.PathLike | None = None) -> RegistryManifest:
    """Load and validate sources/registry.yaml.

    Defaults to sources/registry.yaml relative to the project root
    (two levels up from this file).
    """
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(here, "..", "registry.yaml")
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return RegistryManifest.model_validate(raw)
