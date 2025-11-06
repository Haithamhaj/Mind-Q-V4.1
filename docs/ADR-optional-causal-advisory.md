# ADR: Optional Causal Advisory Stage (09.5)

## Context

Stakeholders requested causal-effect diagnostics between Mind-Q Stages 09 and 10 without altering the validated KPI contracts. The advisory analysis must remain opt-in, respect feature flags, and avoid mutating artefacts from existing stages. We also need downstream BI consumers to treat the insights separately from production KPIs while preserving reproducibility and auditability.

## Decision

We introduced `stage_09_5_causal_inference` as an asynchronous optional phase that activates only when `MINDQ_ENABLE_CAUSAL=true` and a causal problem YAML is supplied. The phase loads read-only outputs from Stage 09, validates data preconditions, estimates treatment effects (DoWhy + CausalML), performs robustness refuters, and emits advisory-only artefacts (`causal_insights.json`, DAG renders, refutation report, recommendations). Every payload is tagged with `advisory_only: true`, uses the mandated “Estimated effect under assumptions” wording, and writes to a dedicated `stage_09_5_causal/` directory.

In Stage 10 we added a safe consumer `include_causal_advisory` that creates an auxiliary `fact_causal_effects.parquet` mart only when the advisory payload is marked `SUPPORTED`. Existing BI marts remain untouched, satisfying the “no KPI recomputation” constraint.

## Consequences

* Pipelines keep backward compatibility: without the flag or problem name the phase returns `{"skipped": true}` and no artefacts are created.
* All advisory outputs are isolated, immutable snapshots tied to the input YAML to support auditing.
* BI dashboards can surface a dedicated “Causal Insights (Advisory)” tab without risking leakage into primary KPI cards.
* Additional dependencies (DoWhy, CausalML, NetworkX, Graphviz) are required for full functionality; the implementation defends against missing optional renderers and will degrade gracefully when they are absent.
