import pandas as pd
import json
from pathlib import Path
import numpy as np
from datetime import datetime

run_id = "smoke-test-02"
base_path = Path(f"artifacts/{run_id}/stage_10_bi")
input_file = base_path / "marts/fact_business.parquet"
output_file = base_path / "datasets/fact_business.json"

print(f"Reading {input_file}...")
df = pd.read_parquet(input_file)

print(f"Converting {len(df)} rows...")

# Convert to records
data = df.to_dict(orient='records')

# Clean NaN, Inf, and Timestamp values
def clean_value(obj):
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
    elif isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return obj

cleaned_data = []
for row in data:
    cleaned_row = {k: clean_value(v) for k, v in row.items()}
    cleaned_data.append(cleaned_row)

# Wrap in {"rows": [...]} structure
output = {"rows": cleaned_data}

# Ensure output directory exists
output_file.parent.mkdir(parents=True, exist_ok=True)

# Write JSON
print(f"Writing to {output_file}...")
with open(output_file, 'w') as f:
    json.dump(output, f)

print(f"✅ Done! Converted {len(cleaned_data)} rows to {output_file}")
print(f"   File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
