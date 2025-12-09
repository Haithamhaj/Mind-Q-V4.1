# Schema Validation (03_schema)

**Group:** Data Foundation  
**Optional:** No

## Goal
Stage 03 extracts a canonical schema for the logistics dataset, aligns it with historical baselines, and produces semantic terminology artifacts that map raw operational headers to business-friendly vocabulary.

## Business Impact
Contributes to data quality and pipeline reliability

## Inputs
- Upstream phase outputs

## Outputs
- Phase artifacts

## Main Code Files
- `phases/03_schema/impl.py`
- `phases/03_schema/terminology.py`
- `backend/src/app/services/stage_03_5_textops/kpi_linker.py`
- `backend/src/app/services/stage_03_5_textops/config_schema.py`
- `backend/src/app/services/stage_03_5_textops/rag_service.py`
- `backend/src/app/services/stage_03_5_textops/emb_openai.py`

## Pipeline Position
**Upstream:** 02_quality
**Downstream:** 03_5_textops

---
*Generated: 2025-12-09T17:45:01.863925*
