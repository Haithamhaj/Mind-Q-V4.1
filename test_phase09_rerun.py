#!/usr/bin/env python3
"""Quick script to re-run Phase 09 and verify bi_feed columns."""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import polars as pl
from phases.phase09_business_validation import impl as phase09

def main():
    run_id = "real-data-test"
    artifacts_root = PROJECT_ROOT / "artifacts"
    
    print(f"Running Phase 09 for run_id: {run_id}")
    print(f"Artifacts root: {artifacts_root}")
    
    inputs = {
        "artifacts_root": artifacts_root,
        "run_id": run_id,
    }
    
    config = {
        "locale": "ar-SA",
        "currency": "SAR",
        "time_grain": "daily",
    }
    
    # Run Phase 09
    print("\n🚀 Running Phase 09...")
    outputs = phase09.run(inputs=inputs, config=config)
    
    # Check results
    bi_feed_path = outputs.get("bi_feed")
    if bi_feed_path and bi_feed_path.exists():
        df = pl.read_parquet(bi_feed_path)
        print(f"\n✅ bi_feed.parquet created successfully!")
        print(f"   Columns: {len(df.columns)}")
        print(f"   Rows: {len(df)}")
        print(f"\n   First 20 columns:")
        for i, col in enumerate(df.columns[:20], 1):
            print(f"      {i}. {col}")
        
        if len(df.columns) > 20:
            print(f"   ... and {len(df.columns) - 20} more columns")
    else:
        print("❌ bi_feed.parquet not created")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
