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
