# PyArrow Failure Forensics (Identification-Only)

## Scope
This report focuses on *identifying* the failure path and problematic column/type mismatch. It does not propose code changes.

## Phase 1 — Deploy Logs Deep Dive

### What was possible locally
- No Railway log artifact is present in this repository, so direct extraction from deploy logs could not be completed in this environment.
- A helper was added to extract all PyArrow-related exceptions from a saved Railway log export:

```bash
python scripts/extract_pyarrow_errors.py /path/to/railway.log
```

Pattern matched by the helper includes:
- `ArrowTypeError`
- `ArrowInvalidError`
- `Expected bytes, got a 'bool' object`
- `Conversion failed for column ...`

## Phase 2 — Locate the Problem DataFrame

### Streamlit display calls in `app.py`

Current render points that eventually route to Arrow conversion:
- `st_dataframe_safe(...)` wrapper calls `st.dataframe(...)` at `app.py:815`.
- Render callsites:
  - `app.py:1325` (provenance rows)
  - `app.py:1382` (case history)
  - `app.py:1551` (batch `rdf` results)
  - `app.py:1662` (process log `proc_df`)
  - `app.py:1754` (discrepancy report)
  - `app.py:2166` (case history table)
  - `app.py:2234` (filtered queue)
  - `app.py:2259` (history view)
  - `app.py:2308` (export manifest)
  - `app.py:1896` (styled OCR extraction table via direct `st.dataframe`)

### DataFrame creation roots

- Structured upload path:
  1. `read_structured(...)` (`app.py:832-848`) creates DataFrame from CSV/XLSX/JSON.
  2. Optional harmonization in `process_file(...)` (`app.py:916-959`).
  3. `clean_dataframe(...)` (`app.py:764-808`).
  4. Rendered later in batch/summary views.

- OCR/LLM path:
  1. `llm_structure(...)` parses JSON (`app.py:887`) and creates `pd.DataFrame(records)` (`app.py:890`).
  2. Then `clean_dataframe(...)` (`app.py:976`).

## Phase 3 — Pinpoint the Column

## Identified mismatch

Reproduced Arrow error with a mixed-type object column:
- Column: `screening_result`
- Mixed values: `"MATCH"` (string) + `True` (boolean)
- Error: `ArrowTypeError ("Expected bytes, got a 'bool' object", "Conversion failed for column screening_result with type object")`

### Where boolean assignment enters the pipeline

The boolean is not assigned by an explicit code line like `df['screening_result'] = True`.
It enters through untyped input materialization:
- `records = json.loads(raw)` at `app.py:887`
- `return pd.DataFrame(records)` at `app.py:890`

If OCR/LLM output includes JSON booleans for categorical text fields, pandas stores them in object columns mixed with strings.

### Git history check

`git blame` for `app.py:887-890` shows the JSON-to-DataFrame path has been present since earlier ingestion changes (April 13, 2026), i.e., this is not a newly introduced assignment line.

## Phase 4 — Reproducible Local Test

Minimal reproduction script:

```bash
python scripts/reproduce_pyarrow_bool_mismatch.py
```

Expected output includes:
- object dtype for `screening_result`
- mixed Python types `['str', 'bool', 'str']`
- Arrow conversion failure with the exact bool/bytes mismatch

## Phase 5 — Clear Finding

### Direct answers

1. **What column has the problem?**
   - `screening_result` (confirmed via minimal repro with mixed `str`/`bool`).

2. **Which file and line causes the boolean assignment?**
   - No explicit assignment statement exists.
   - The value enters via untyped JSON parsing in `app.py:887-890` (`json.loads` → `pd.DataFrame(records)`).

3. **Which Streamlit call triggers the display?**
   - Any `st.dataframe` route can trigger Arrow conversion; the wrapper call is at `app.py:815`, with active callsites listed above.

4. **What is the exact data mismatch?**
   - A pandas `object` column expected to be textual contains booleans and strings in the same column.
   - Representative mismatch: `screening_result = ["MATCH", True, "NO_MATCH"]`.
