# Changelog

## Phase 3 — Dimension Schema Normalization (2026-04-28)

### Changed
- All six core dimensions (`IdentityVerification`, `AccountActivity`, `ProofOfAddressDimension`, `DataQuality`, `AMLScreening`, `BeneficialOwnership`) now emit a root `score: int` (0–100) in every code path, including error and missing-data paths.
- `AMLScreeningDimension`: `aml_status` and `aml_hit_status` moved from the result root into `evaluation_details`. Engine reads them from `evaluation_details`.
- `KYCComplianceEngine.evaluate_customer()`: removed `_extract_score()` adapter helper and the pass/fail fallback approximation (80/40). Scores are now read directly from `result["score"]` for all six core dimensions.

### Added
- `kyc_engine/dimensions/schema.py`: `DimensionResult` required-key set and `validate_dimension_result()` helper for contract enforcement.
- `tests/test_dimension_schema.py`: 13 schema-contract tests covering all six core dimensions and the validator itself.

### Deferred
- SOW (`SourceOfWealthDimension`) and CRS (`CRSFATCADimension`) schema migration (engine uses `.get("score", fallback)` shim for these two).

## [0.4.0] — 2026-04-19

### Added
- `rules/kyc_rules_v2.0.json` — jurisdiction-aware ruleset with
  FATF/Wolfsberg baseline and 8 jurisdiction overlays:
  USA (FinCEN/OFAC/OCC), GBR (FCA/JMLSG), EU (EBA/BaFin/ACPR/CSSF),
  CHE (FINMA), SGP (MAS), HKG (HKMA/SFC), AUS (AUSTRAC).
  China placeholder present, deferred post-v1.
- `rules/schema/dimensions.py` — `JurisdictionOverlay` model with
  `jurisdiction_code`, `regulators`, `dimension_overrides`,
  `additional_hard_reject_rules`, `additional_review_rules`.
- `rules/schema/ruleset.py` — `RulesetManifest.jurisdictions` dict field.
- `kyc_engine/ruleset.py` — `get_jurisdiction_params(jurisdiction_code)`
  deep-merges baseline dimension params with jurisdiction overrides.
- `kyc_engine/ruleset.py` — `get_jurisdiction_rules(jurisdiction_code)`
  combines baseline rules with jurisdiction-specific additional rules.
- `kyc_engine/engine.py` — jurisdiction routing in `evaluate_customer()`:
  reads `jurisdiction` column from customer record, fetches merged params,
  passes to all 6 dimension classes.
- `kyc_engine/engine.py` — `_extract_score()` replaces blunt
  `passed → 80 / failed → 40` approximation with actual dimension score.
- `evaluate_customer()` result now includes `"jurisdiction"` key.

### Key regulatory deltas encoded in v2.0 overlays
- HKG: SFC UBO threshold 10% (vs FATF baseline 25%)
- SGP: MAS PSN01 transaction velocity window 30 days (vs baseline 90)
- EU: 6AMLD rescreening interval 180 days (vs baseline 365)
- CHE: FINMA rescreening 180 days, velocity window 60 days
- GBR: FCA doc expiry warning 60 days (vs baseline 90)

### Tests
- `test_ruleset_schema.py` — 4 new `TestJurisdictionMergeLogic` tests
- `test_pwm_regression.py` — 3 new `TestJurisdictionRouting` tests
- Total: 45 passed (up from 38 at end of Phase 2)

### Deferred
- China (CHN) overlay present as placeholder; all params fall back
  to baseline until post-v1 regulatory source coverage is complete.
- Residual inline AML scoring in `evaluate_customer()` (TODO marked).
- `kyc_engine/models.py` still absent — plain dicts returned by engine.

## v0.2.0 — 2026-04-18
Phase 0 structural separation. No behavioral changes.
- Split app.py (2,351 lines) into kyc_engine/, kyc_dashboard/, kyc_audit/, kyc_llm/
- kyc_engine/ is importable with zero Streamlit dependencies (verified by pytest)
- Fixed double _build_export_package call in export flow
- Fixed sys.path injection in load_engine()
- Removed duplicate anthropic import
- 11 tests passing

## v0.1.0 — 2026-04-14
Initial ruleset v1.0. Baseline PWM disposition rules.

## v0.3.0 — Phase 2: Engine Refactor: Rules-as-Data
- kyc_engine/ruleset.py created; load_ruleset() returns validated RulesetManifest
- Engine loads kyc_rules_v1.1.json; all dimension thresholds read from
  dimension_parameters (no hardcoded constants in dimension classes)
- System B (BaseDimension subclasses) replaces System A inline methods as live evaluator
- RULESET_VERSION unified: single source of truth via get_active_ruleset_version()
- data_quality.critical_fields patched in v1.1 JSON to match actual engine CSV schema
- HR-004 now triggers on empty DataFrame, None, missing key, and sentinel string
- Synthetic PWM regression suite: 14 cases covering all dispositions and all 6 dimensions
- No user-observable behavioral changes; evaluate_customer() return shape preserved
