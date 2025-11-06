#!/usr/bin/env python3
"""Test script to verify dynamic BI feed column selection logic."""

import polars as pl
from pathlib import Path

# Simulate the _bi_feed logic from Phase 09
def test_dynamic_selection():
    # Read Phase 06 output
    phase06_path = Path("artifacts/real-data-test/stage_06_standardize/clean.parquet")
    source_df = pl.read_parquet(phase06_path)
    
    print(f"📥 Phase 06 Input: {len(source_df.columns)} columns, {len(source_df)} rows")
    
    # Simulate required columns (from Phase 09)
    REQUIRED_FACT_COLUMNS = [
        "entity_id", "ts", "ORIGIN", "DESTINATION", "RECEIVER_MODE", "STATUS", "COD_AMOUNT",
        "kpi_orders_cnt", "kpi_cod_total", "kpi_cod_avg", "kpi_cod_rate",
        "kpi_sla_pct", "kpi_rto_pct", "kpi_lead_time_p50", "kpi_lead_time_p90",
        "eff_effect_size", "eff_confidence", "eff_coverage_p90",
        "eff_stability_time_pct", "eff_stability_segment_pct",
        "eff_simpson_flag", "eff_small_n_flag",
        "decision", "explain_key", "row_deeplink",
        "tz", "locale", "currency", "time_grain", "scenario_id",
    ]
    
    # Add entity_id and ts if missing
    feed = source_df
    if "entity_id" not in feed.columns:
        feed = feed.with_row_count("entity_id")
    if "ts" not in feed.columns:
        feed = feed.with_columns(pl.lit(None).alias("ts"))
    
    # Dynamic column selection logic (from lines 762-791)
    final_columns = REQUIRED_FACT_COLUMNS.copy()
    
    excluded_columns = set()  # No policy map for testing
    column_policy_map = {}
    
    # Add missing required columns
    for col in REQUIRED_FACT_COLUMNS:
        if col not in feed.columns:
            feed = feed.with_columns(pl.lit(None).alias(col))
    
    # DYNAMIC SELECTION: Include ALL columns from Phase 06
    for col in feed.columns:
        if col not in final_columns and col not in excluded_columns:
            # Skip missing indicators
            if col.endswith('__is_missing') or col.endswith('_is_missing'):
                continue
            # Skip required columns already added
            if col in REQUIRED_FACT_COLUMNS:
                continue
            # Include everything else
            final_columns.append(col)
    
    # Select final columns
    bi_feed = feed.select(final_columns)
    
    print(f"\n📤 BI Feed Output: {len(bi_feed.columns)} columns")
    print(f"\n✅ Dynamic columns added: {len(bi_feed.columns) - len(REQUIRED_FACT_COLUMNS)}")
    
    # Show columns breakdown
    required_set = set(REQUIRED_FACT_COLUMNS)
    dynamic_cols = [col for col in bi_feed.columns if col not in required_set]
    
    print(f"\n📊 Column Breakdown:")
    print(f"   Required columns: {len(REQUIRED_FACT_COLUMNS)}")
    print(f"   Dynamic columns:  {len(dynamic_cols)}")
    print(f"   Total:            {len(bi_feed.columns)}")
    
    print(f"\n📋 Dynamic columns added (first 30):")
    for i, col in enumerate(dynamic_cols[:30], 1):
        print(f"   {i:3d}. {col}")
    
    if len(dynamic_cols) > 30:
        print(f"   ... and {len(dynamic_cols) - 30} more")
    
    # Save test output
    output_path = Path("test_bi_feed.parquet")
    bi_feed.write_parquet(output_path)
    print(f"\n💾 Saved test output to: {output_path}")
    
    return bi_feed

if __name__ == "__main__":
    bi_feed = test_dynamic_selection()
    print(f"\n🎉 Test completed successfully!")
