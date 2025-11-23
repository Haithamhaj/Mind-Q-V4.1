import pandas as pd
from pathlib import Path

path = Path("artifacts/smoke-test-01/stage_03_5_textops/structured_fields.parquet")
if not path.exists():
    print(f"File not found: {path}")
    exit(1)

df = pd.read_parquet(path)
print(f"Loaded {len(df)} rows")
print(f"Columns: {df.columns.tolist()}")

join_candidates = ["AWB_NO", "awb_no", "shipment_id", "SHIPMENT_ID"]
for col in join_candidates:
    if col in df.columns:
        dupes = df[col].duplicated().sum()
        print(f"Column '{col}': {dupes} duplicates found")
        if dupes > 0:
            print(df[df[col].duplicated(keep=False)][col].head())
