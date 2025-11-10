# Changelog

## [0.5.0] - 2025-11-10
- Added new delivery timestamp aliases (`DELIVERED_AT`/`DELIVERED_TIMESTAMP`) so Stage 09 reliably finds POD events without manual overrides.
- Centralized `low_signal_warn_threshold` under `config/params.yml`, snapshotting drift to telemetry and surfacing it as a `threshold_drift` log.
- Audited `geo_indicator_only` flows inside Stage 05; integrity violations now trip `geo_indicator_only_modified` warnings and show up in metrics.
- Introduced the `enable_knime_stub` flag (default `false`) to keep KNIME bridge stubs out of production artifacts unless explicitly requested.
- Moved the Stage 08 contract to `contracts/bi/story_v1.1.schema.json` and updated tooling/tests to read from the shared location.
- Added a 0.75 MB cap to Stage 08 advanced JSON exports, logging and summarizing any truncated KNIME payloads.
- Locked `requirements*.txt` (including `ftfy`) with hashes/markers so CI installs deterministic wheels.
- Extended CI with `tools/check_phases_imports.py` to prevent runtime modules from importing `phases.*` directly.
- Published run-governance artifacts (`artifacts/reports/ci_run_report.json`, `stage_size_report.json`) consumed by CI for the dry vs. real execution check.
