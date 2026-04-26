# Dashboard Merge Bundle

This bundle contains the files changed while porting `dashboard.md` into the modular Streamlit app located at:

`/Users/lucabacci/Downloads/KYC_Apexon-Jupyter_Branch`

## What is in this bundle

- `kyc_dashboard/main.py`
- `kyc_dashboard/components.py`
- `kyc_dashboard/state.py`
- `kyc_dashboard/tabs/dashboard.py`
- `kyc_dashboard/tabs/data_documents.py`
- `kyc_audit/logger.py`
- `users.json`

## Functional changes included

1. Removed the old `Individual Evaluation` and `Batch Results` navigation tabs.
2. Added a new leftmost `Dashboard` tab with:
   - batch-backed queue run
   - pass/fail metrics
   - filters
   - queue table
   - customer drill-down pane
3. Added `Banker` role:
   - only `Data & Documents` visible
   - customer names hidden
   - document preview hidden
4. Added Admin dashboard-local access to:
   - `Audit Trail`
   - `Ruleset Editor`
5. Added audit event type:
   - `RULESET_UPDATED`

## Important note about the current GitHub checkout

The GitHub checkout at:

`/Users/lucabacci/Documents/Codex/2026-04-17-github-plugin-github-openai-curated-https/KYC_Apexon`

is on branch `Jupyter_Branch`, but it is not the same structure as this modular app folder. It also already has a local modification in `app.py`.

Because of that, this bundle was prepared as a source-of-truth handoff rather than an automatic merge.

## Recommended merge approach

1. Open the current GitHub branch in a real git checkout.
2. Compare its app structure to this modular bundle.
3. Port the dashboard behavior in this order:
   - `kyc_dashboard/tabs/dashboard.py`
   - `kyc_dashboard/main.py`
   - `kyc_dashboard/tabs/data_documents.py`
   - `kyc_dashboard/state.py`
   - `kyc_dashboard/components.py`
   - `kyc_audit/logger.py`
   - `users.json`
4. Resolve any existing `app.py` changes manually.

## Validation already done

- Python syntax check passed on the changed files with `python3 -m py_compile`
- `users.json` parses successfully

## Not validated here

- `pytest` was not available in this environment
- The target GitHub checkout was not auto-merged because of structure drift and existing local changes
