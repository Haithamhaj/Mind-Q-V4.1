import pandas as pd
import json
from pathlib import Path

run_id = "smoke-test-02"
base_path = Path(f"artifacts/{run_id}/stage_10_bi")
marts_path = base_path / "marts/fact_business.parquet"
semantic_path = base_path / "semantic"

print(f"Reading {marts_path}...")
df = pd.read_parquet(marts_path)

# Analyze columns
date_cols = []
numeric_cols = []
categorical_cols = []
bool_cols = []

for col in df.columns:
    dtype = df[col].dtype
    
    if pd.api.types.is_datetime64_any_dtype(dtype):
        date_cols.append({"name": col})
    elif pd.api.types.is_bool_dtype(dtype):
        bool_cols.append({"name": col})
    elif pd.api.types.is_numeric_dtype(dtype):
        numeric_cols.append({"name": col})
    else:
        # Check if it's a date string
        if col.lower().endswith('_date') or col.lower() == 'ts':
            date_cols.append({"name": col})
        else:
            categorical_cols.append({"name": col})

# Create dimensions catalog
dimensions_catalog = {
    "generated_at": pd.Timestamp.now().isoformat(),
    "row_count": len(df),
    "date": date_cols,
    "numeric": numeric_cols,
    "categorical": categorical_cols,
    "bool": bool_cols
}

# Create metrics catalog from KPI columns
metrics = []
for col in df.columns:
    if col.startswith('kpi_'):
        metric_id = col.replace('kpi_', '')
        metrics.append({
            "id": metric_id,
            "title": metric_id.replace('_', ' ').title(),
            "formula": f"MAX({col})",
            "unit": "count" if "cnt" in col else "amount" if "total" in col or "avg" in col else "ratio",
            "fmt": "integer" if "cnt" in col else "sar_currency" if "total" in col or "avg" in col else "percentage",
            "time_col": "ts"
        })

# Save files
semantic_path.mkdir(parents=True, exist_ok=True)

dims_file = semantic_path / "dimensions_generated.json"
with open(dims_file, 'w') as f:
    json.dump(dimensions_catalog, f, indent=2)
print(f"✅ Saved dimensions to {dims_file}")

metrics_file = semantic_path / "metrics_generated.json"
with open(metrics_file, 'w') as f:
    json.dump(metrics, f, indent=2)
print(f"✅ Saved metrics to {metrics_file}")

print(f"\nSummary:")
print(f"  Date columns: {len(date_cols)}")
print(f"  Numeric columns: {len(numeric_cols)}")
print(f"  Categorical columns: {len(categorical_cols)}")
print(f"  Bool columns: {len(bool_cols)}")
print(f"  Metrics (KPIs): {len(metrics)}")
