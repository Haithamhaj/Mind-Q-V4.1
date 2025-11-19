# Stage 11 – ML Lab (Offline Experiments)

## Purpose
Stage 11 is a developer-facing sandbox (typically Colab/Jupyter) for exploring data, training candidate models, and documenting experiments before promoting them to the production inference catalog that Stage 09 consumes.

## Workflow
1. **Fetch data** – export Stage 06/10 datasets into `notebooks/ml_lab/data/` (keep the exact subset for reproducibility).
2. **Notebook runs** – configure deterministic seeds, run experimentation notebooks, and capture metrics/bias checks.
3. **Persist artifacts**:
   - Serialized estimator under `artifacts/models/<model_key>/<version>.pkl`
   - Structured report in `artifacts/ml_lab/ml_lab_report_<date>.json`
4. **Catalog update** – edit `contracts/models/models_catalog.yml` with the new version/path plus optional feature list and report pointer.
5. **Review checklist** – confirm accuracy deltas, PSI drift, fairness metrics, and reviewer sign-off before merging.

## Tips
- Keep notebooks deterministic (set `numpy`, `pandas`, `sklearn`, and framework seeds).
- Use cloud storage for large raw exports, but copy the sampled subset into `notebooks/ml_lab/data/` for auditing.
- Follow the supplied `ml_lab_report_example.json` when documenting experiments; every catalog entry should link back to a report.
- Stage 09 remains inference-only; **never** run `.fit()` inside pipeline stages.
