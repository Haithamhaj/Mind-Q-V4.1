# Quality Checks (02_quality)

**Group:** Data Foundation  
**Optional:** No

## Goal
Stage 02 validates the ingested dataset against logistics-specific quality gates, cataloguing issues, enforcing row-count baselines, and signaling schema drift before downstream enrichment or modeling begins.

## Business Impact
Contributes to data quality and pipeline reliability

## Inputs
- Upstream phase outputs

## Outputs
- Phase artifacts

## Main Code Files
- `phases/02_quality/impl.py`

## KPIs
- Drift
- Quality

## Pipeline Position
**Upstream:** 01_ingestion
**Downstream:** 03_schema

---
*Generated: 2025-12-09T17:29:57.826481*
