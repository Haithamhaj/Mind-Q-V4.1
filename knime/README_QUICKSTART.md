# 🔬 KNIME Workflow - Quick Test Guide

## الوضع الحالي
> Stage 07 now includes an interactive "KNIME Bridge" prompt in the pipeline. Approving it prepares `artifacts/<run_id>/phase_07_knime/` automatically (data copy, schema, KPI map, and `run_meta.json`). Use `MINDQ_KNIME_MODE=auto` to auto-approve or `MINDQ_KNIME_MODE=skip` to suppress the prompt.
تم إنشاء KNIME workflow بسيط يتكون من:
1. **Input Loader**: يقرأ ملفات Parquet من `${input_dir}`
2. **DQ Validator**: يطبق فحوصات جودة البيانات الأساسية
3. **Output Writer**: يكتب النتائج إلى `${output_dir}`

## طريقة التشغيل

### الخيار 1: تشغيل من GUI
```pwsh
# افتح KNIME مع موافقة واحدة
pwsh -File scripts/run_knime.ps1 -ApprovalCount 1
```

ثم داخل KNIME:
1. File → Import KNIME Workflow → Browse → اختر `knime/phase07_feature_app.knwf`
2. Flow Variables → اضبط:
   - `input_dir` = `C:\Github - MindQ\Mind-Q-V4-BI\artifacts\run-latest\stage_10`
   - `output_dir` = `C:\Github - MindQ\Mind-Q-V4-BI\artifacts\run-latest\phase_07_knime`
3. Run → Execute All

### الخيار 2: تشغيل Batch من PowerShell
```pwsh
# جهّز المجلد المطلوب
New-Item -ItemType Directory -Path "artifacts/run-latest/phase_07_knime" -Force

# شغّل KNIME workflow
pwsh -File knime/run_knime_workflow.ps1 -RunId "run-latest" -AutoApprove
```

⚠️ **ملاحظة**: السكربت يتوقع البيانات في `artifacts/run-latest/phase_07_knime/` لكن بياناتك الحالية في `artifacts/run-latest/stage_10/`

### الخيار 3: انسخ البيانات للموقع المتوقع
```pwsh
# انسخ البيانات من stage_10 إلى phase_07_knime
$source = "artifacts/run-latest/stage_10/data.parquet"
$dest = "artifacts/run-latest/phase_07_knime"

New-Item -ItemType Directory -Path $dest -Force
Copy-Item $source -Destination "$dest/data.parquet"

# شغّل KNIME
pwsh -File knime/run_knime_workflow.ps1 -RunId "run-latest" -AutoApprove
```

## عرض النتائج
بعد التشغيل، النتائج ستكون في:
- `artifacts/run-latest/phase_07_knime/features_validated.parquet`

لعرضها:
```pwsh
# اقرأ النتائج بواسطة Python
python -c "import polars as pl; df = pl.read_parquet('artifacts/run-latest/phase_07_knime/features_validated.parquet'); print(df.head())"
```

أو افتح KNIME GUI وشوف الجداول مباشرة.

## التطوير المستقبلي
هذا workflow بسيط جداً. لتحسينه:
1. أضف 55 قاعدة DQ من `contracts/dq/rules_inventory.yml`
2. أضف KPI calculations
3. أضف FDR-corrected insights
4. اربطه مع Python scripts الموجودة (validate_dq_coverage.py، إلخ)

## استكشاف الأخطاء
- إذا KNIME ما فتح: تأكد من `$env:KNIME_HOME` يشير لـ `tools\knime\knime_5.5.1`
- إذا workflow ما اشتغل: افتحه في GUI أول وجرب Execute يدوي
- إذا Python node فشل: تأكد من ربط Python في KNIME (File → Preferences → KNIME → Python)
