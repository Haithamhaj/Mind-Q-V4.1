# Phase 03.5 - TextOps

Phase 03.5 ingests Phase 03 dictionaries plus raw shipment text and produces both numeric features and evidence artifacts for later stages.

## Inputs
- Shipments parquet files (`raw/shipments/*.parquet`) containing `AWB_NO` or `shipment_id`, free text columns, and timestamps.
- Phase 03 dictionary artifacts (`artifacts/{run_id}/stage_03/...`).
- Optional raw document and notes directories for future expansion.

## Outputs
Artifacts are written to `artifacts/{run_id}/stage_03_5_textops/`:
- `sentiment_features.parquet`: lite sentiment, density metrics, language codes and timestamps.
- `svd_components.parquet`: hashed vector representation reduced via SVD.
- `tfidf_info.json`: vectorizer metadata.
- `text_profile.json`: top terms, keyphrases, masked examples, and runtime metadata.
- `textops_report.json`, `quality_findings.json`, `_READY.OK`, and `manifest.json` for orchestration.

## Processing flow
1. Load runtime configuration (`config/textops.yaml`) and resolve artifacts root.
2. Read shipments dataset, pick the available join key (`AWB_NO` or `shipment_id`).
3. Normalise and mask text columns (Arabic/English canonicalisation, diacritics strip, digit unification, rule-based PII placeholders).
4. Build language codes, density metrics, lite sentiment scores, and hashed vectors (HashingVectorizer + TruncatedSVD).
5. Generate top terms/keyphrases, masked examples, evidence profile, and aggregate statistics.
6. Enforce data contracts (join key completeness, PII guard, thresholds for coverage, language conflicts, SVD variance).
7. Persist artefacts, compute hashes, emit manifest and ready flag.

## Configuration
`config/textops.yaml` centralises runtime options:
- Normalisation and privacy switches.
- Vectorisation settings (hash feature space and SVD components).
- Thresholds for STOP/WARN decisions.
- Optional embeddings/RAG placeholders for future activation.
- `embeddings.api_key` أو `llm.credentials_file` تسمح بتمرير المفتاح مباشرة؛ إن تُركت فارغة تُحمّل المرحلة القيم من ملفات ‎`.env` بنفس أسلوب المرحلة 10.

## Testing
- Unit tests cover normalisation, masking, density metrics, vectorisation metadata, and contract guards.
- Integration test synthesises a shipments dataset (≥10k rows) and validates artefact schemas, join key integrity, coverage metrics, and readiness flag.

## Integration notes
- Pipeline API (`src/app/services/pipeline_api/app.py`) now exposes `/v1/runs/{run_id}/phases/03/textops` and schedules Phase 03.5 between Schema and Profile.
- Phase manifest and results view reference `stage_03_5_textops` outputs for Insights Phase (08) consumption.
- Config placeholders (`config/kpi_map.yaml`, `config/dim_keys.yaml`) keep compatibility with future LLM/RAG enhancements.
## LLM & RAG (Optional)
- When `embeddings.provider="openai"` and `rag.enabled=true`, Phase 3.5 chunks shipment/document text, stores segments in `doc_segments.parquet`, builds an embeddings map, and emits a FAISS index (`embeddings.faiss`).
- Enabling `llm.enabled=true` triggers structured extraction tasks (`extract_sla`, `extract_sop`, `summarize`). Results are written to `rules_sla_llm.parquet`, `sop_steps_llm.parquet`, `company_profile_llm.parquet`, `contacts_llm.parquet`, with linkage hints in `kpi_links.parquet` and traces recorded in `llm_trace.jsonl`.
- Missing API credentials or context gracefully raise WARN findings (`rag_error`, `llm_error`) without stopping the numeric pipeline.

- Vector store can be switched via `vector_store.type` (faiss | qdrant). When `qdrant` is selected, set connection details under `vector_store.qdrant`; the stage pushes embeddings to Qdrant in addition to the local FAISS index and records warnings if the endpoint is unreachable.
