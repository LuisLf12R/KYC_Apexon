# DataFrame Lineage Inventory, Hardening Checklist, and Monitoring Guide

## 1) Survey: DataFrame display inventory and lineage

## Streamlit display inventory (`app.py`)

| Display line | DataFrame variable | Created at | Source lineage |
|---|---|---|---|
| `1325` | `pd.DataFrame(prov_rows)` | inline | provenance store rows |
| `1382` | `pd.DataFrame(history)` | inline | session history accumulator |
| `1551` | `rdf` | `1442` | `results[]` from engine evaluations |
| `1662` | `proc_df` | `1661` | file processing status rows |
| `1754` | `disc_df` | `1752` | discrepancy collector rows |
| `1897` | styled `display_df` | `1885-1888` | OCR/LLM extraction summary |
| `2166` | `pd.DataFrame(c["case_history"])` | inline | case history events |
| `2234` | `filtered` | `2224-2231` | audit logger dataframe filters |
| `2259` | `show_df` | `2257` | provenance history rows |
| `2308` | `pd.DataFrame(pkg["manifest"])` | inline | export package manifest |

## Primary DataFrame creation points

- `read_structured` (CSV/XLSX/JSON/JSONL) at `app.py:832-848`
- `llm_structure` (`json.loads` → `pd.DataFrame`) at `app.py:887-890`
- `process_file` orchestration at `app.py:908-977`

## 2) Prevention at source

- `llm_structure` now hardens the DataFrame immediately after JSON parsing by calling `ensure_arrow_compatible(...)`.
- `clean_dataframe` also runs `ensure_arrow_compatible(...)` with dataset context.

## 3) Defense at render time

- `st_dataframe_safe(...)` applies `ensure_arrow_compatible(...)` before `st.dataframe(...)` for DataFrame inputs.
- Styled OCR extraction table now hardens `display_df` before rendering.

## 4) Local + staging + production checklist

### Local validation
- [ ] `pytest -q`
- [ ] `pytest -q tests/test_arrow_integration_flow.py`
- [ ] `pytest -q tests/test_streamlit_e2e_smoke.py`
- [ ] `python scripts/reproduce_pyarrow_bool_mismatch.py`

### Railway staging deployment
- [ ] Deploy current commit to staging.
- [ ] Upload a known-problem screening file containing mixed bool/string statuses.
- [ ] Confirm no `ArrowTypeError` in logs.
- [ ] Run `python scripts/extract_pyarrow_errors.py <exported-staging-log.txt>`.

### First 24h monitoring in production
- [ ] Export logs every 4 hours and run `extract_pyarrow_errors.py`.
- [ ] Track count of `ArrowTypeError`/`Conversion failed for column` entries.
- [ ] Record top offending column names (if any) and payload source (structured vs OCR/LLM).
- [ ] Declare healthy if error count remains zero after 24h.

## 5) Best practices

1. Harden immediately after untyped ingestion (`json.loads`, `read_json`, external API payloads).
2. Keep textual enum fields as `StringDtype`, never mixed bool/string objects.
3. Normalize nested structures (dict/list) before UI rendering.
4. Reuse a single hardening utility (`ensure_arrow_compatible`) for both source and display defense.
5. Add integration tests whenever new display tables or ingestion paths are introduced.

## 6) Optional pre-commit linter

Consider adding pre-commit hooks for format/lint/test smoke:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.13
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
```

This is optional and can be introduced incrementally.
