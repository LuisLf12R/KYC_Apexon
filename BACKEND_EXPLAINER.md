# KYC Apexon — Backend Architecture Explainer

> **Stack:** Python 3.13 · FastAPI · Pandas · Anthropic Claude API · Google Cloud Vision  
> **Deployment:** Render.com (Docker) · `kyc-apexon.onrender.com`  
> **Ruleset:** `kyc_rules_v2.1.json`

---

## High-Level Architecture

```
Browser (atlas-kyc-dashboard/)
        │
        │  HTTP / JSON
        ▼
┌─────────────────────────────────┐
│  FastAPI  (backend/main.py)     │  ← auth, routing, in-memory state
│                                 │
│  ┌─────────────┐  ┌──────────┐  │
│  │  Pipeline   │  │  Utils   │  │
│  │ (pipeline.py│  │(utils.py)│  │
│  └──────┬──────┘  └────┬─────┘  │
│         │              │        │
│  ┌──────▼──────────────▼─────┐  │
│  │     KYC Engine            │  │
│  │  (kyc_engine/engine.py)   │  │
│  │  8 scoring dimensions     │  │
│  └───────────────────────────┘  │
│                                 │
│  ┌────────────┐  ┌────────────┐ │
│  │  Audit     │  │ AI Obs.   │ │
│  │ (audit_    │  │(ai_observ-│ │
│  │  state.py) │  │ ability.py│ │
│  └────────────┘  └────────────┘ │
└─────────────────────────────────┘
        │
        │  Temp filesystem
        ▼
  /tmp/kyc_data_clean/
  customers_clean.csv
  screenings_clean.csv
  transactions_clean.csv
  documents_clean.csv
  id_verifications_clean.csv
  beneficial_ownership_clean.csv
```

---

## 1. Entry Point & Serving

**`backend/main.py`** is the FastAPI app. It also mounts the frontend:

```python
app.mount("/", StaticFiles(directory="atlas-kyc-dashboard", html=True))
```

So `GET /` serves `atlas-kyc-dashboard/index.html`, and all `/api/...` routes are handled by FastAPI before the static fallback.

`GET /admin` → redirects to `/` (legacy route, kept for compatibility).

---

## 2. Authentication

Simple bearer-token session system — no database, tokens live in-memory.

| Endpoint | What it does |
|---|---|
| `POST /api/auth/login` | Checks `users.json` → issues a UUID token stored in `SESSIONS` dict |
| `POST /api/auth/logout` | Removes token from `SESSIONS` |

Credentials are in **`users.json`** at the repo root. Protected endpoints use `_require_session()` as a FastAPI dependency — reads `Authorization: Bearer <token>` or `X-Auth-Token` header.

Two roles: **`admin`** (full access) and **`banker`** (limited — no audit trail, no ruleset editing).

---

## 3. File Upload Pipeline

**`POST /api/upload`** accepts any mix of CSVs, Excel, JSON, PDF, PNG, JPG in one multipart request.

Each file goes through **`backend/pipeline.py`**:

```
File bytes
    │
    ├─ Structured (.csv/.xlsx/.json)
    │       │
    │       ├── _read_structured()      → pandas DataFrame
    │       ├── _harmonize_columns()    → normalise column names
    │       └── _detect_dataset_type()  → guess: customers / screenings / transactions /
    │                                            documents / id_verifications /
    │                                            beneficial_ownership
    │
    └─ Unstructured (.pdf/.png/.jpg)
            │
            ├── _run_ocr()             → Google Vision API (images)
            │                          → pdfplumber / pdfminer (PDFs)
            ├── _detect_dataset_type() → filename keywords first
            │                            (passport→documents, statement→documents, etc.)
            └── _llm_structure()       → Claude claude-sonnet-4-6 extracts structured rows
                                         from raw OCR text
    │
    └── _save() → appends/overwrites /tmp/kyc_data_clean/<type>_clean.csv
```

**Dataset type detection priority:**
1. Explicit `dataset_type` field in the multipart form (user override)
2. Filename keywords: `passport`, `utility`, `bill`, `statement` → `documents`; `screening` → `screenings`; etc.
3. Column fingerprinting: presence of `screening_id`, `transaction_id`, `document_id`, etc.
4. Falls back to `customers` if nothing matches

Uploaded document bytes are also stored in **`_DOC_VAULT`** (in-memory dict) keyed by filename so `GET /api/documents/preview/{filename}` can serve them back for in-app preview. Vault clears on server restart.

---

## 4. KYC Batch Evaluation

**`POST /api/kyc/batch`** is the main evaluation trigger.

```
Load all 6 clean CSVs from /tmp/kyc_data_clean/
        │
        ▼
KYCComplianceEngine.evaluate_all()
        │
        ├── For each customer_id:
        │       └── evaluate_customer()
        │               ├── AMLScreeningDimension        (weight 25%)
        │               ├── IdentityVerificationDimension (weight 20%)
        │               ├── AccountActivityDimension      (weight 15%)
        │               ├── BeneficialOwnershipDimension  (weight 15%)
        │               ├── ProofOfAddressDimension       (weight 10%)
        │               ├── SourceOfWealthDimension       (weight  8%)
        │               ├── DataQualityDimension          (weight  5%)
        │               └── CRSFATCADimension             (weight  2%)
        │
        ├── overall_score = weighted average (0–100)
        │
        └── determine_disposition()
                ├── Any REJECT rule triggered?  → REJECT  (regardless of score)
                ├── Any REVIEW rule triggered?  → REVIEW
                ├── score ≥ pass_min?           → PASS
                ├── score ≥ notes_min?          → PASS_WITH_NOTES
                └── else                        → REVIEW
```

Results are:
1. Returned in the HTTP response as `{ results: [...], summary: { total, flagged } }`
2. Stored in **`_LAST_BATCH`** (in-memory) for re-fetching via `GET /api/batch-results`
3. Manual approve/reject overrides in **`APPROVALS`** dict are applied before returning

**Evaluation date:** anchored to the most recent event date in the uploaded data (not today's date). This prevents time-based checks from false-flagging historical datasets.

---

## 5. Scoring Dimensions

Each dimension lives in `kyc_engine/dimensions/` and returns a score 0–100 plus structured flags.

| Dimension | Weight | Key signals |
|---|---|---|
| **AML Screening** | 25% | `screening_result` (NO_MATCH→85, POSSIBLE_MATCH→50, CONFIRMED_MATCH→10), `resolution_status`, PEP/sanctions flags, screening staleness vs evaluation date |
| **Identity Verification** | 20% | Document verified status, expiry date vs evaluation date, verification method (BIOMETRIC > MANUAL) |
| **Account Activity** | 15% | `is_suspicious` transaction flags, high-risk counterparty countries (IR, KP, SY, RU), structuring patterns, transaction volume |
| **Beneficial Ownership** | 15% | UBO verification completeness, UBO PEP/sanctions flags, ownership chain depth |
| **Proof of Address** | 10% | Document status (VERIFIED/PENDING/EXPIRED), expiry date |
| **Source of Wealth** | 8% | SoW category present and recognised, corroboration with transaction patterns |
| **Data Quality** | 5% | Critical fields present (`customer_id`, `full_name`, `jurisdiction`, `risk_rating`), no duplicate records |
| **CRS / FATCA** | 2% | `crs_status` and `fatca_status` compliance flags |

Ruleset thresholds (from `kyc_rules_v2.1.json`):
- **REJECT:** any hard rule triggered (e.g. `sanctions_flag=TRUE`, `CONFIRMED_MATCH`)
- **REVIEW:** any soft rule triggered (e.g. `pep_flag=TRUE`, `POSSIBLE_MATCH`, missing documents)
- **PASS:** score ≥ `pass_min` threshold with no rule triggers

---

## 6. API Reference

### Auth
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | ✗ | Returns bearer token |
| POST | `/api/auth/logout` | ✓ | Invalidates token |

### Upload & Batch
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/upload` | ✓ | Upload 1–N files; returns per-file status, rows, detected type |
| POST | `/api/kyc/batch` | ✓ | Run full evaluation on uploaded data |
| GET | `/api/batch-results` | ✗ | Return last batch results (survives navigation, clears on restart) |
| GET | `/api/kyc/customer/{id}` | ✓ | Evaluate a single customer on demand |
| POST | `/api/kyc/approve/{id}` | ✓ | Override disposition → Cleared |
| POST | `/api/kyc/reject/{id}` | ✓ | Override disposition → Escalated |

### Documents
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/documents/preview/{filename}` | ✗ | Serve uploaded file bytes for in-app preview |

### System
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health` | ✗ | Liveness check |
| GET | `/api/institutions` | ✓ | List available institutions |
| GET | `/api/system/info` | ✓ | Framework version, ruleset, hosting config |
| GET | `/api/ruleset` | ✓ | Full ruleset JSON |
| GET | `/api/ai-observability` | ✗ | AI usage tracker (currently returns empty — card shows static estimates) |
| GET | `/api/audit` | ✓ | Full audit trail |
| POST | `/api/audit/log` | ✗ | Append a frontend navigation event |

---

## 7. In-Memory State

The server is stateless across restarts — all state lives in Python dicts:

| Variable | Type | Contents | Cleared on restart? |
|---|---|---|---|
| `SESSIONS` | dict | `token → {user_id, role, …}` | ✅ Yes |
| `APPROVALS` | dict | `customer_id → "approved"\|"rejected"` | ✅ Yes |
| `_DOC_VAULT` | dict | `filename → (bytes, mime_type)` | ✅ Yes |
| `_LAST_BATCH` | dict | Last batch `results` + `summary` | ✅ Yes |

Persistent state lives in `/tmp/kyc_data_clean/` (the 6 clean CSVs). This directory survives across requests but is wiped when the container restarts (Render ephemeral filesystem).

---

## 8. Audit Trail

**`backend/audit_state.py`** — singleton `AuditLogger` writes to an in-memory list.

Every significant action is logged: `UPLOAD_FILE`, `BATCH_RUN_START`, `BATCH_RUN_COMPLETE`, `CASE_APPROVED`, `CASE_REJECTED`, `NAV_*` (frontend navigation events), etc.

`GET /api/audit` groups events by category (Upload, Evaluation, Approval, Navigation) and returns them with actor, timestamp, batch ID, and structured details.

---

## 9. Deployment

```
GitHub (Jupyter_Branch)
    │  push
    ▼
Render.com (Docker)
    │
    ├── Builds from Dockerfile (python:3.13-slim)
    ├── Installs requirements.txt
    └── CMD: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Required env vars on Render:**
| Var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API (LLM structuring of uploaded documents) |
| `GOOGLE_CREDENTIALS_JSON` | Google Cloud Vision (OCR for PDF/images) |
| `API_BASE_URL` | Public URL injected into the frontend config |
| `PORT` | Set by Render automatically |

**`users.json`** at repo root defines credentials. Default admin: `admin / atlas2024`.
