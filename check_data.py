import polars as pl

# Load the business data
df = pl.read_parquet('artifacts/run-20251016085938/stage_09_business_validation/bi_feed.parquet')

print(f"Total rows: {len(df)}")
print(f"Columns: {df.columns}")
print(f"RECEIVER_MODE values:")
print(df["RECEIVER_MODE"].value_counts())
print(f"DESTINATION unique count: {df['DESTINATION'].n_unique()}")
print(f"DESTINATION top 10:")
print(df["DESTINATION"].value_counts().head(10))
print(f"TS null count: {df['ts'].null_count()} out of {len(df)}")

# Check COD data
print(f"COD_AMOUNT stats:")
print(df.select("COD_AMOUNT").describe())
print(f"kpi_orders_cnt stats:")
print(df.select("kpi_orders_cnt").describe())