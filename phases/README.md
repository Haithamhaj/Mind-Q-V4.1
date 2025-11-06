# Phases mapping

This file explains the directory layout under `phases/` and maps the human-friendly phase numbers (1 → 7) and sub-phases to the actual folder names present in this branch.

Use the branch view (tree) for a full file listing:

- Branch (full tree): https://github.com/Haithamhaj/Mind-Q-V4.1/tree/port/update-2025-10-11
- Pull Request: https://github.com/Haithamhaj/Mind-Q-V4.1/pull/1

## Mapping (human phase → directory)

- Phase 1 — Ingestion
  - `01_ingestion/` and alternate compatibility ` _01_ingestion/`

- Phase 2 — Quality
  - `02_quality/`

- Phase 3 — Schema
  - `03_schema/`

- Phase 3.5 — (Feature report / interim)
  - `07_5_feature_report/`  <!-- this repo uses a 07_5_* folder for the feature-report step; treated as a mid-pipeline auxiliary step -->

- Phase 4 — Profiling
  - `04_profile/`

- Phase 5 — Missing values handling
  - `05_missing/`

- Phase 6 — Standardize & Feature engineering
  - `06_standardize/`
  - `06_feature_eng/`

- Phase 7 — Readiness, LLM summary and final reporting
  - `07_readiness/`
  - `07_6_llm_summary/`  (LLM summarization step)

## Notes
- Some directories exist with alternate naming (e.g. `_01_ingestion`) to support different import strategies. The runner can import either.
- If a reviewer is missing files in the PR view, ask them to open the Branch tree link (above) to view the complete file list.
- If you want me to rename folders to match exact numeric ordering (e.g. `03_5` or `07_6` -> `07_6_llm_summary` is already descriptive), I can prepare a migration patch but merging/renaming may require coordinating with CI and other branches.

If anything here is incorrect or you'd like different labels, tell me and I will update this README.
