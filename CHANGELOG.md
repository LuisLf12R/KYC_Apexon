# Changelog

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
