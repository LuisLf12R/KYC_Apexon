# DataFrame → Arrow Conversion Hardening Plan

## Phase 1: Inventory

### Conversion points in this project

The runtime failure occurs when Streamlit converts pandas DataFrames to Arrow for `st.dataframe(...)` rendering. In this codebase, these render points are concentrated in `app.py` and now route through `st_dataframe_safe(...)`.

Primary conversion points:
- Batch results table
- Processing log table
- Discrepancy table
- Case history / provenance / manifest tables

### Full pipeline map (structured uploads)

1. Upload file through Data Management tab.
2. Parse into pandas DataFrame (`read_structured`).
3. Optional schema harmonization (`SchemaHarmonizer.normalize`).
4. Canonical cleanup (`clean_dataframe`).
5. Save cleaned CSVs (`save_to_temp`).
6. Engine reload (`load_engine`).
7. Render output tables (`st_dataframe_safe` → `make_arrow_compatible`).

### Column type/schema inspection

Use this command against any failing dataset:

```powershell
python - << 'PY'
import pandas as pd
p = r"<path-to-your-csv>"
df = pd.read_csv(p)
print(df.dtypes)
for c in df.columns:
    vals = df[c].dropna().head(20).tolist()
    types = sorted({type(v).__name__ for v in vals})
    if len(types) > 1:
        print(f"MIXED: {c} -> {types}")
PY
```

### Test vs production data compare

Compare same columns in both datasets and flag mixed object columns:

```powershell
python - << 'PY'
import pandas as pd

def summarize(path):
    df = pd.read_csv(path)
    out = {}
    for c in df.columns:
        vals = df[c].dropna().head(100)
        out[c] = sorted({type(v).__name__ for v in vals})
    return out

prod = summarize(r"<prod.csv>")
test = summarize(r"<test.csv>")
for c in sorted(set(prod) | set(test)):
    if prod.get(c) != test.get(c):
        print(c, "prod=", prod.get(c), "test=", test.get(c))
PY
```

## Phase 2: Root Cause

### Exact failing column pattern

Root-cause signature: **object column expected as text contains mixed booleans + strings/lists/dicts**. Typical offenders:
- `screening_result`
- `hit_status`
- `document_status`
- OCR/LLM-derived free-text fields

### Where boolean values sneak in

- OCR+LLM extraction can emit JSON booleans (`true`/`false`) for categorical fields.
- Mixed manual/API records can provide booleans where text enums are expected.

### pandas / PyArrow compatibility check

Run in your virtual environment:

```powershell
python - << 'PY'
import pandas, pyarrow
print("pandas", pandas.__version__)
print("pyarrow", pyarrow.__version__)
PY
```

Recommended practice: keep modern compatible pairs (e.g., pandas 2.x with recent pyarrow).

## Phase 3: Implementation

Implemented safeguards:

1. `coerce_expected_text_columns(...)` casts expected text/categorical fields to StringDtype before downstream transformations.
2. `make_arrow_compatible(...)` normalizes mixed object columns (bool/list/dict/bytes/mixed types) into Arrow-safe strings.
3. `st_dataframe_safe(...)` enforces conversion safety for Streamlit display paths.

Edge cases handled:
- `NaN`, `None`, `pd.NA` preserved as nulls.
- Empty strings normalized to nulls.
- dict/list/tuple/set converted to JSON text.

## Phase 4: Testing

### Unit tests added

- Boolean leakage in canonical text columns
- Mixed object columns for display conversion
- Missing/empty value handling

Run:

```powershell
pytest tests/test_dataframe_arrow_compat.py -q
```

### End-to-end staging validation checklist

1. Upload one known-good batch and one historically failing batch.
2. Confirm no Streamlit Arrow conversion error in UI or logs.
3. Confirm status/category columns still appear correctly upper-cased.
4. Confirm CSV export still round-trips.

### Deployment checklist

- [ ] Run unit tests in CI and Railway build.
- [ ] Validate versions (`pandas`, `pyarrow`) in Railway image.
- [ ] Smoke test Data Management + Batch Evaluation tabs.
- [ ] Monitor first production upload logs for Arrow conversion warnings.
