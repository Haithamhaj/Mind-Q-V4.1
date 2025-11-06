# External Adapters Guide

هذا الملف يلخّص مكوّنات الـ adapters الاختيارية، الأعلام المطلوبة، والاختلافات بين الـ baseline و الـ adapter outputs.

## نظرة سريعة

| المرحلة | الـ baseline | الـ adapter | العلم | الاعتماد الخارجي | المخرجات الإضافية | إشارات الـ logs/BI | اختبار محلي |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Stage 03.5 – Document Field Extraction | Regex فقط (`docs_textqa_baseline`) | لا يوجد DocVQA حالياً | `USE_EXT_DOCUMENT_FIELD_EXTRACTION=1` | `pdfminer.six` (اختياري) | `document_field_predictions.json` | يظهر عند تفعيل العلم مع تحذيرات عند الخطأ | — |
| Stage 08 – KPI Anomaly Scoring | Z-score baseline | PyOD IsolationForest (`score_kpi_anomalies`) | `USE_EXT_KPI_ANOMALY_SCORING=1` | `pyod` | لا توجد ملفات إضافية، لكن `anomalies.method` = `adapter` | log الحدث `anomaly_detection` يسجل `method` و metadata | `tests/adapters/test_anomaly_pyod.py` |
| Stage 09.5 – Causal Root Cause Hints | Summaries بدون DoWhy | DoWhy ATE (`build_root_cause_hints_payload`) | `USE_EXT_ROOT_CAUSE_HINTS=1` | `dowhy` | `root_cause_hints.json` | payloads و logs تحفظ `method=adapter` | `tests/adapters/test_causal_dowhy.py` |
| Stage 12 – Routing / VRPTW | Greedy deterministic fallback | OR-Tools VRPTW solver | `USE_EXT_VRPTW_SOLVER=1` | `ortools` | `route_plan.json` يحمل `method` و `arrival_times` | log `routing_plan` يعرض `method` و `unassigned` | `tests/adapters/test_routing_ortools.py` |

## تفاصيل إضافية

### Stage 03.5 TextOps
- يبقى regex baseline هو الخيار الوحيد حالياً. عند تفعيل العلم يتم حفظ نتائج regex إلى `document_field_predictions.json` فقط عندما يوجد محتوى قابِل للاستخراج.
- في حال فشل القراءة أو فقدان التبعيات يتم الاكتفاء بتحذير في الـ logs ولا تتوقف المرحلة.

### Stage 08 Insights (Anomaly)
- baseline: تحليل z-score لكل المجموعات مع `sigma=3.0` و `min_n=300`.
- عند تفعيل العلم يتم بناء تجميع PyOD عبر `score_kpi_anomalies`. في حال نجاحه تُحدّث قائمة `anomaly_records` وتُسجَّل metadata (`model`, `contamination`, `selected`).
- في حالة الخطأ أو عدم وجود مجموعات كافية يبقى baseline كما هو مع تحذير `anomaly_adapter_warning`.

### Stage 09.5 Causal Inference
- baseline يكتب `causal_insights.json` مع `method` = baseline.
- عند تفعيل العلم وتوفر common causes يُنشأ `root_cause_hints.json` ويُسجَّل `method=adapter` في كل الـ payloads (insights, summary, refute, recommendations) بالإضافة إلى الـ logs.
- إذا غابت common causes أو فشل DoWhy يبقى baseline ويُذكر السبب في log.

### Stage 12 Routing
- greedy fallback يمر على العقد حسب السعة بدون أي اعتماد خارجي.
- عند تفعيل العلم يستخدم OR-Tools مع time windows و capacity dimension؛ في حال التعثر يعود للـ baseline مع تحذير `routing_adapter_warning`.
- خطط OR-Tools تحفظ أوقات الوصول (`arrival_times`) وتضمن زيارة كل العقد.

## أوامر التشغيل المحلية

```bash
pip install -r requirements-adapters.txt
export USE_EXT_KPI_ANOMALY_SCORING=1
export USE_EXT_FORECAST_TEMPLATES=1
export USE_EXT_ROOT_CAUSE_HINTS=1
export USE_EXT_VRPTW_SOLVER=1
pytest -q   tests/adapters/test_anomaly_pyod.py   tests/adapters/test_timeseries_statsforecast.py   tests/adapters/test_routing_ortools.py   tests/adapters/test_causal_dowhy.py
```
