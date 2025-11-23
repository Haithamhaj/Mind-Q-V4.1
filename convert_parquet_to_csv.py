import pandas as pd
from pathlib import Path

parquet_path = Path("artifacts/smoke-test-02/stage_10_bi/marts/fact_business.parquet")
csv_path = Path("Final_Report.csv")

if not parquet_path.exists():
    print(f"Error: Parquet file not found at {parquet_path}")
    exit(1)

print(f"Reading {parquet_path}...")
df = pd.read_parquet(parquet_path)
print(f"Loaded {len(df)} rows and {len(df.columns)} columns.")

print(f"Writing to {csv_path}...")
df.to_csv(csv_path, index=False)
print("Conversion complete.")
