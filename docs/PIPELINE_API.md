# Pipeline FastAPI Gateway

يوضح هذا الدليل كيفية تشغيل واجهة FastAPI الجديدة التي تعرض كل مراحل Mind-Q كخدمات HTTP قابلة للتكامل (من المرحلة 01 حتى 09) إضافة إلى تشغيل المسار الكامل دفعة واحدة.

## المتطلبات
- Python 3.11 مع الاعتمادات المحدّثة (`fastapi`, `uvicorn`, `openai`, `duckdb`، إلخ) — مثبتة مسبقاً عبر `pyproject.toml`.
- ضبط `PYTHONPATH=src` قبل تشغيل الخادم حتى يتمكن من استيراد الحزم الداخلية:
  ```powershell
  $env:PYTHONPATH = "src"
  ```
- يتم إنشاء المجلد `artifacts/` تلقائياً إن لم يكن موجوداً.

## تشغيل الخادم
```powershell
uvicorn app.services.pipeline_api.app:app --host 0.0.0.0 --port 9000 --reload
```

### فحص الصحة
```bash
curl http://localhost:9000/healthz
```

## المراحل الفردية (REST)
جميع الاستجابات تعيد JSON من دالة `run` لكل مرحلة. أمثلة:

### 1. المرحلة 01 – ingestion
```bash
curl -X POST http://localhost:9000/v1/runs/fastcoo/phases/01/ingestion \
     -H "Content-Type: application/json" \
     -d '{
           "data_files": ["C:/data/Fastcoo_LM_Data.csv"],
           "sla_files": ["C:/contracts/fastcoo_sla.pdf"]
         }'
```

### 2. المرحلة 02 – quality
```bash
curl -X POST http://localhost:9000/v1/runs/fastcoo/phases/02/quality \
     -H "Content-Type: application/json" \
     -d '{}'          # use_defaults=true بشكل افتراضي
```

نفس النمط ينطبق على بقية المراحل:
- `/v1/runs/{run_id}/phases/03/schema`
- `/v1/runs/{run_id}/phases/04/profile`
- `/v1/runs/{run_id}/phases/05/missing`
- `/v1/runs/{run_id}/phases/06/standardize` (يعيد نتائج standardize & feature_eng)
- `/v1/runs/{run_id}/phases/07/readiness`
- `/v1/runs/{run_id}/phases/07/feature-report`
- `/v1/runs/{run_id}/phases/07/llm-summary` (يتطلب مفاتيح LLM عند `llm_summary=true`)
- `/v1/runs/{run_id}/phases/08/insights`
- `/v1/runs/{run_id}/phases/09/business-validation`
- `/v1/runs/{run_id}/phases/09_5_causal` (?????? ????? causal advisory - OPT-IN)

تمكين `use_defaults=false` يسمح بتمرير مسارات الإدخال أو إعدادات مخصصة:
```bash
curl -X POST http://localhost:9000/v1/runs/fastcoo/phases/05/missing \
     -H "Content-Type: application/json" \
     -d '{
           "use_defaults": false,
           "inputs": {"raw": "C:/artifacts/run/stage_01_ingestion/raw.parquet"},
           "config": {"missing": {"strategy_override": "groupwise"}}
         }'
```

## تشغيل المسار الكامل
```bash
curl -X POST http://localhost:9000/v1/runs/fastcoo/pipeline/full \
     -H "Content-Type: application/json" \
     -d '{
           "data_files": ["C:/data/Fastcoo_LM_Data.csv"],
           "sla_files": ["C:/contracts/fastcoo_sla.csv"],
           "llm_summary": false,
           "stop_on_error": true
         }'
```
يعيد الرد قائمة بالنتائج لكل مرحلة. إذا `stop_on_error=true` سيعيد خطأ HTTP عند أول مرحلة تُرجع STOP.

## ملاحظات
- المرحلة 08 تحتاج ملفات `correlations.json` و`redundancy.json`. إذا كانت متوفرة فقط تحت `stage_07_readiness/` يقوم الخادم بنسخها تلقائياً إلى `stage_07_correlations/` قبل التشغيل.
- المرحلة 09 تعتمد على DuckDB وPolars لإعادة حساب KPI؛ تم تضمين تطعيم بسيط لـ `polars.Series.apply` لضمان العمل مع الإصدارات الحديثة.
- Endpoint المرحلة 07.6 لن يُنفّذ إلا إذا تم ضبط مفاتيح المزود (`OPENAI_API_KEY` أو غيره) أو عند تمرير `llm_summary=false` لمسار pipeline الكامل.

## دمج مع الأنظمة الأخرى
- يمكن للمستهلك الخارجي استدعاء أي مرحلة بشكل منفصل، والحصول على تقرير JSON لوضعها (PASS/WARN/STOP) إضافة إلى مسارات artifacts الناتجة.
- يوصى بحفظ ردود الـ API في مستودع تدقيق جانبي لضمان إمكانية التتبع للـ run_id والملفات المستخدمة.

