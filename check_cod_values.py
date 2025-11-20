import polars as pl

# قراءة البيانات
df = pl.read_parquet('/Users/haitham/development/Mind-Q-V4.1-port/artifacts/run-20251120171848/stage_06_feature_eng/features.parquet')

print("=== COD_AMOUNT Analysis ===")
print(f"Total rows: {df.height}")
print(f"Null count: {df['COD_AMOUNT'].null_count()}")
print(f"Zero count: {(df['COD_AMOUNT'] == 0).sum()}")
print(f"\nValue counts:")
print(df['COD_AMOUNT'].value_counts().head(10))
print(f"\nStats:")
print(df['COD_AMOUNT'].describe())
print(f"\nMin: {df['COD_AMOUNT'].min()}")
print(f"Max: {df['COD_AMOUNT'].max()}")
print(f"Mean: {df['COD_AMOUNT'].mean()}")
