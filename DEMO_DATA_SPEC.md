# KYC Demo Data Generation Spec
Hand this file to any LLM (Qwen, Gemini, GPT-4, etc.) with the instruction:
> "Generate a fresh KYC demo dataset following this spec. Output each CSV as a fenced code block."

---

## What to produce
Six CSV files. All customers must share IDs across files (customer_id is the join key).
Use **50 customers** per batch. Target outcome mix: **~60% PASS · ~25% REVIEW · ~15% REJECT**.
Create the actual documents not just code, do it in a zip folder to download

Use today's date as the reference point. Keep all screening/verification/upload dates within the last 90 days. Keep document expiry dates 1–6 years in the future (except for REJECT customers — give them expired or rejected docs).

---

## Customer ID format
`KYC-XXXX` where XXXX is a 4-digit number. Start from a number above 0060 to avoid colliding with existing demo data (e.g. start at KYC-0101).

---

## File 1 — `customers.csv`

| Column | Type | Valid values / notes |
|---|---|---|
| `customer_id` | string | KYC-XXXX |
| `full_name` | string | Real-sounding name or company name |
| `jurisdiction` | string | 2-letter ISO country code (CH, GB, SG, AE, JP, FR, DE, US, HK, LU, CA, AU) |
| `client_type` | string | `INDIVIDUAL` or `CORPORATE` |
| `tier` | string | `WEALTH`, `UHNW`, `FAMILY_OFFICE` |
| `risk_rating` | string | `LOW`, `MEDIUM`, `HIGH` |
| `onboarding_date` | date | YYYY-MM-DD, within the last 3 years |
| `aum` | number | Numeric only, no symbols. WEALTH: 100K–2M, UHNW: 2M–50M, FAMILY_OFFICE: 5M–200M |
| `relationship_manager` | string | Use `A. Mercer` for all rows |
| `pep_flag` | bool | `TRUE` or `FALSE`. Set TRUE for REVIEW customers |
| `sanctions_flag` | bool | `TRUE` or `FALSE`. Set TRUE for REJECT customers |
| `nationality` | string | 2-letter ISO code, usually matches jurisdiction |
| `date_of_birth` | date | YYYY-MM-DD for INDIVIDUAL only, blank for CORPORATE |
| `country_of_residence` | string | 2-letter ISO code |
| `source_of_wealth` | string | `INVESTMENT`, `EMPLOYMENT`, `BUSINESS_INCOME`, `INHERITANCE`, `REAL_ESTATE` |
| `tax_id` | string | Freeform, e.g. `CH48291034` |
| `crs_status` | string | `COMPLIANT`, `NON_COMPLIANT`, `NOT_APPLICABLE` |
| `fatca_status` | string | `COMPLIANT`, `NON_COMPLIANT`, `NOT_APPLICABLE` (NOT_APPLICABLE for non-US) |

**REJECT customers:** `sanctions_flag=TRUE`, `risk_rating=HIGH`, `crs_status=NON_COMPLIANT`
**REVIEW customers:** `pep_flag=TRUE`, `risk_rating=HIGH` or `MEDIUM`
**PASS customers:** both flags FALSE, `risk_rating=LOW` or `MEDIUM`

---

## File 2 — `screenings.csv`

| Column | Type | Valid values / notes |
|---|---|---|
| `customer_id` | string | Must match a customer |
| `screening_date` | date | Within last 60 days |
| `screening_result` | string | `NO_MATCH`, `POSSIBLE_MATCH`, `CONFIRMED_MATCH` |
| `risk_rating` | string | `LOW`, `MEDIUM`, `HIGH` |
| `resolution_status` | string | `CLEARED`, `UNDER_REVIEW`, `ESCALATED` |
| `resolution_date` | date | YYYY-MM-DD if CLEARED, blank otherwise |
| `match_name` | string | Similar name to customer if POSSIBLE/CONFIRMED, blank if NO_MATCH |
| `match_score` | number | 0 if NO_MATCH, 55–75 if POSSIBLE_MATCH, 85–98 if CONFIRMED_MATCH |
| `list_reference` | string | e.g. `PEP-WORLD`, `OFAC-SDN`, `EU-SANCTIONS`, blank if NO_MATCH |

**REJECT:** `CONFIRMED_MATCH` + `ESCALATED` + high match_score (85+) + real sanctions list
**REVIEW:** `POSSIBLE_MATCH` + `UNDER_REVIEW` + resolution_date blank
**PASS:** `NO_MATCH` + `CLEARED` + match_score=0

---

## File 3 — `transactions.csv`

| Column | Type | Valid values / notes |
|---|---|---|
| `customer_id` | string | Must match a customer |
| `transaction_date` | date | Within last 90 days |
| `transaction_type` | string | `WIRE_TRANSFER`, `DEPOSIT`, `INVESTMENT`, `CASH_DEPOSIT`, `WITHDRAWAL` |
| `amount` | number | Numeric only |
| `currency` | string | 3-letter ISO code (USD, EUR, CHF, GBP, SGD, JPY, AED) |
| `counterparty_country` | string | 2-letter ISO code |
| `is_suspicious` | bool | `TRUE` or `FALSE` |
| `transaction_id` | string | TXN-XXXX, unique |
| `channel` | string | `ONLINE`, `BRANCH`, `MOBILE` |

**REJECT:** 2–3 transactions with `is_suspicious=TRUE`, large amounts (>$200K), counterparty countries include `IR`, `KP`, `SY`, or `RU`
**REVIEW/PASS:** `is_suspicious=FALSE`, counterparty countries match customer jurisdiction or major financial hubs

Give each customer 2–3 transactions.

---

## File 4 — `documents.csv`

| Column | Type | Valid values / notes |
|---|---|---|
| `customer_id` | string | Must match a customer |
| `document_type` | string | `PASSPORT`, `PROOF_OF_ADDRESS`, `CERTIFICATE_OF_INCORPORATION`, `UTILITY_BILL`, `BANK_STATEMENT` |
| `document_id` | string | DOC-XXXX, unique |
| `upload_date` | date | Within last 60 days |
| `status` | string | `VERIFIED`, `PENDING`, `EXPIRED`, `REJECTED` |
| `file_name` | string | e.g. `sophie_passport.pdf` |
| `issuing_country` | string | 2-letter ISO code |
| `expiry_date` | date | Future date for VERIFIED docs (1–8 years out); past date for EXPIRED |

**REJECT:** at least one `EXPIRED` or `REJECTED` document
**PASS/REVIEW:** all docs `VERIFIED` or `PENDING` with future expiry

Give each customer 2 documents (passport/cert + proof of address).

---

## File 5 — `id_verifications.csv`

| Column | Type | Valid values / notes |
|---|---|---|
| `customer_id` | string | Must match a customer |
| `document_type` | string | `PASSPORT`, `DRIVERS_LICENSE`, `CERTIFICATE_OF_INCORPORATION` |
| `verification_date` | date | Within last 60 days |
| `expiry_date` | date | Future for PASS/REVIEW; past for REJECT |
| `verification_method` | string | `BIOMETRIC`, `MANUAL`, `VIDEO_CALL` |
| `name_on_document` | string | Must match `full_name` in customers.csv |

One row per customer.

---

## File 6 — `beneficial_ownership.csv`

Only include rows for **CORPORATE** customers. Skip INDIVIDUAL customers entirely.

| Column | Type | Valid values / notes |
|---|---|---|
| `customer_id` | string | CORPORATE customers only |
| `ubo_name` | string | Full name of the beneficial owner |
| `ubo_dob` | date | YYYY-MM-DD |
| `ubo_nationality` | string | 2-letter ISO code |
| `ownership_percent` | number | All UBOs for a customer must sum to 100 |
| `ubo_role` | string | `CEO`, `DIRECTOR`, `SOLE_OWNER`, `CFO`, `TRUSTEE` |
| `ubo_pep_flag` | bool | `TRUE` or `FALSE` |
| `ubo_sanctions_flag` | bool | `TRUE` or `FALSE` |
| `ubo_jurisdiction` | string | 2-letter ISO code |
| `verification_date` | date | Within last 60 days |
| `chain_depth` | number | `1` for direct ownership |
| `parent_ownership_pct` | number | Same as `ownership_percent` for direct |
| `control_type` | string | `DIRECT`, `INDIRECT` |

---

## Expected outcome summary

Include a short comment block at the top of your response listing:
- Each customer name, their ID, and their expected result (PASS / REVIEW / REJECT)
- One-line reason for each REVIEW and REJECT

---

## Realism rules
- Names: mix of European, Asian, Middle Eastern, Latin American — no fictional or obviously fake names
- Companies: realistic fund/wealth management names (e.g. "Kestrel Capital AG", "Horizon Trust Ltd")
- AUM amounts: don't round to millions — use specific numbers like 3,847,200 not 4,000,000
- Dates: vary them, don't use the same date for every row
- Do NOT reuse names, IDs, or amounts from this example:
  > KYC-0051 Sophie Laurent, KYC-0052 Meridian Capital, KYC-0053 Ahmad Al-Rashidi,
  > KYC-0054 Chen Wei Holdings, KYC-0055 Isabelle Fontaine, KYC-0056 Viktor Drakov,
  > KYC-0057 Haruki Tanaka, KYC-0058 Carla Mendez Ortega
