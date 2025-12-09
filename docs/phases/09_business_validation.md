# Business Validation (09_business_validation)

**Group:** Business Intelligence  
**Optional:** No

## Goal
Stage 09 Business Validation reconciles operational KPIs, SLA contracts, and Stage 08 insights into governed fact tables, action plans, and BI feeds.

## Business Impact
Contributes to data quality and pipeline reliability

## Inputs
- Upstream phase outputs

## Outputs
- Phase artifacts

## Main Code Files
- `phases/09_business_validation/impl.py`
- `phases/09_business_validation/models.py`
- `phases/09_business_validation/io.py`
- `backend/src/app/services/stage_09_5_causal_inference/config_loader.py`
- `backend/src/app/services/stage_09_5_causal_inference/refute.py`
- `backend/src/app/services/stage_09_5_causal_inference/dag.py`

## KPIs
- SLA

## Pipeline Position
**Upstream:** 08_insights
**Downstream:** 09_5_causal

---
*Generated: 2025-12-09T17:29:57.839345*
