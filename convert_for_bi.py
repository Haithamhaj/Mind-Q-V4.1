import pandas as pd
from pathlib import Path
import json

run_id = "smoke-test-02"
base_path = Path(f"artifacts/{run_id}/stage_10_bi")
marts_path = base_path / "marts/fact_business.parquet"
output_path = base_path / "datasets/fact_business.json"

if not marts_path.exists():
    print(f"Error: {marts_path} not found")
    exit(1)

print(f"Reading {marts_path}...")
df = pd.read_parquet(marts_path)

# Ensure output directory exists
output_path.parent.mkdir(parents=True, exist_ok=True)

print(f"Writing to {output_path}...")
# Convert to records format for frontend consumption
# The frontend provider expects { rows: [...] } or just [...]
# Let's wrap it in rows to match the provider logic:
# if (data && data.rows && Array.isArray(data.rows)) ...
records = df.to_dict(orient="records")
output_data = {"rows": records}

with open(output_path, "w") as f:
    json.dump(output_data, f, default=str) # handle dates

print("Conversion complete.")
