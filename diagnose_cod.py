import pandas as pd

# 1. مسار ملفك الأصلي (عدله حسب مكان الملف)
raw_file_path = '/Users/haitham/development/Mind-Q-V4.1-port/data/Fastcoo_LM_Data_full.csv'
# 2. مسار ملف المخرجات قبل الـ Insights مباشرة
stage_07_path = '/Users/haitham/development/Mind-Q-V4.1-port/artifacts/run-20251120171848/stage_06_feature_eng/features.parquet'

print("--- DIAGNOSIS START ---")

# فحص الملف الخام
try:
    if raw_file_path.endswith('.csv'):
        df_raw = pd.read_csv(raw_file_path, nrows=5)
    else:
        df_raw = pd.read_excel(raw_file_path, nrows=5)
    
    print(f"\n[Raw File] Columns found: {list(df_raw.columns)}")
    # البحث عن أي عمود يشبه COD
    cod_candidates = [c for c in df_raw.columns if 'COD' in str(c).upper() or 'AMOUNT' in str(c).upper()]
    print(f"[Raw File] Potential COD columns: {cod_candidates}")
    
    if cod_candidates:
        print(f"[Raw File] First 5 values in '{cod_candidates[0]}':")
        print(df_raw[cod_candidates[0]].tolist())
except Exception as e:
    print(f"[Error reading Raw File]: {e}")

# فحص ملف المرحلة 07
try:
    df_proc = pd.read_parquet(stage_07_path)
    print(f"\n[Stage 07] Columns found: {list(df_proc.columns)}")
    
    if 'COD_AMOUNT' in df_proc.columns:
        nulls = df_proc['COD_AMOUNT'].isnull().sum()
        total = len(df_proc)
        print(f"[Stage 07] COD_AMOUNT Nulls: {nulls} / {total} ({nulls/total*100:.1f}%)")
    else:
        print("[Stage 07] ALERT: 'COD_AMOUNT' column is COMPLETELY MISSING from the dataframe.")
except Exception as e:
    print(f"[Error reading Stage 07]: {e}")

print("\n--- DIAGNOSIS END ---")
