# وثيقة التكامل مع KNIME (Stage 07 Bridge)

## 1. الهدف والنطاق
- شرح كيفية تجهيز المرحلة 07 لمدّ KNIME بالمدخلات القياسية وقراءة المخرجات.
- توثيق خيارات التشغيل (Prompt/Auto/Skip) ومسار الموافقات والسكربتات المساندة.
- تغطية الاعتمادات بين المراحل (Stage 06، Stage 07.5، Stage 08) وما ينتج عنها من ملفات.

## 2. نظرة سريعة على التدفق
1. مرحلة Stage 06 تنشر ملف الميزات `features.parquet`.
2. مرحلة Stage 07_5 تنتج ملفات تحليل إضافية (`variance_analysis.json`, `comparative_summary.json`, `heatmap_matrix.json`).
3. عند استدعاء `stage_07_knime_bridge.run` يتم تجهيز مجلد `artifacts/<run_id>/phase_07_knime/` وتشغيل محرك التحليلات البايثوني (`backend/src/app/services/stage_07_analytics`).
4. يتم نسخ البيانات، السكيمة، خريطة الـ KPI، تقارير الجاهزية، وملف `run_meta.json` إلى مجلد phase_07_knime.
5. يتم بناء `layer2_candidate.json`, `bridge_summary.json`, `dq_report.json`, `dq_coverage_summary.json`, `insights_fdr.json` ونسخها أيضًا إلى `artifacts/<run_id>/stage_07_knime_bridge/profile/` لاحتياجات الـ API.
6. يتم إنشاء `phase_07_knime/outputs/` و`phase_07_knime/transforms/analytics/` بنسخة من نتائج Python (clusters/anomalies/correlations/forecast) ليتعامل `/api/bi/...` معها دون أي اعتماد على KNIME Desktop.

### 2.1 خط بيانات BI الفعلي بعد إزالة KNIME
```
stage_06_feature_eng/features.parquet
    → stage_07_knime_bridge (Python BI prep)
        • phase_07_knime/{data.parquet, profile/, transforms/analytics}
    → stage_08_insights (src/app/services/stage_08_insights/impl.py)
        • layer2_candidate + analytics outputs
    → stage_09_business_validation (phases/09_business_validation/impl.py)
        • bi_feed.parquet, row_decisions.parquet
    → phase10_bi (phases/phase10_bi/impl.py)
        • marts/fact_business.parquet, datasets/orders.parquet
    → /api/bi/orders + /api/bi/metrics + /api/bi/intelligence (src/app/api/bi.py)
        • phase_07_knime/profile/* + stage_10_bi/marts/*
```

## 3. ضبط وضعية التشغيل
- الدالة `_resolve_mode` تقرأ المفاتيح `bi_prep_mode` أو `mode` (مع دعم الاسم القديم `knime_mode`)، ثم القيم البيئية `MINDQ_BI_PREP_MODE` أو `BI_PREP_MODE` (ويتم قبول `MINDQ_KNIME_MODE`/`KNIME_PIPELINE_MODE` فقط لضمان التوافق الرجعي)، مع دعم الأعلام `auto_approve` و`auto_skip` (`src/app/services/stage_07_bi_prep_python/impl.py`).
- القيم الممكنة: `auto` (تشغيل محرك Python مباشرة) و`skip` (يتجاهل التحضير ويعيد حالة SKIP). أي قيمة أخرى يتم تحويلها تلقائياً إلى `auto`.
- لا يوجد تفاعل يدوي أو سكربت خارجي؛ كل المخرجات تُبنى تلقائياً.

## 4. الملفات التي يتم تجهيزها
- `phase_07_knime/data.parquet`: نسخة من Stage 06.
- `phase_07_knime/schema.json`: يتم البحث عنها حسب الأولوية (Stage 03، ثم `contracts/schema.json`).
- `phase_07_knime/kpi_map.yml`: من Stage 06 أو fallback إلى `backend/contracts/kpis.yml`.
- `phase_07_knime/profile/`: يحتوي نسخًا من `readiness_report.json`, `decision_manifest.json`, `feature_report.json`، بالإضافة إلى ملفات Python الجديدة (`dq_report.json`, `dq_coverage_summary.json`, `insights_fdr.json`, `run_summary.md`, `analytics_summary.json`).
- `phase_07_knime/outputs/`: نسخة من نتائج `stage_07_analytics` (مثل `dq_summary.json`, `cluster_summary.json`, `anomalies.json`, `correlation_matrix.json`, `forecast.parquet`).
- `phase_07_knime/transforms/analytics/`: يُعاد نسخ الملفات السابقة كتحويلات جاهزة لاستهلاك `/api/bi` بنفس واجهة KNIME القديمة.
- `phase_07_knime/run_meta.json`: يتضمن `run_id`, `workflow`, `git_sha`, `git_branch`, مصادر الملفات، وملخص جودة البيانات (`impl.py:198`).
- `phase_07_knime/profile/bridge_summary.json`: يلخص ما تم نسخه مع التوقيت والوضع (`impl.py:223`).
- `layer2_candidate.json`: يُبنى من مخرجات Stage 07_5 أو يتم إنشاء قالب فارغ مع ملاحظة غياب البيانات (`impl.py:107`).
- يتم نسخ `bridge_summary.json`, `layer2_candidate.json`, `feature_report.json` إلى `stage_07_knime_bridge/profile/` لضمان التناسق مع طبقات BI.

## 5. خيارات التشغيل المتقدمة
- تمت إزالة أعلام `run_batch`/`only_execute`/`auto_execute`، لأن المرحلة باتت تبني المخرجات داخلياً.
- حقل `metrics` يعرض الآن حالة `python_analytics` (نجاح/تخطي/تحذير) وعدد الصفوف/الأعمدة التي تم تحضيرها.

## 6. بوابة الموافقات
- تمت أرشفة سكربت `scripts/knime_approval.ps1` والأعلام المرتبطة به. لم تعد هناك حاجة لأي موافقة يدوية أو رصيد تشغيلات، إذ يعمل الـ BI Prep بالكامل داخل Python.
- في حال الحاجة لأي تكامل قديم، يمكن الرجوع إلى السكربت كمرجع تاريخي فقط دون أن يكون جزءاً من المسار الرسمي.

## 7. تشغيل KNIME Batch
> **ملاحظة:** تم إيقاف تشغيل KNIME batch من خط الـ BI الرسمي. يمكن الرجوع إلى السكربت `knime/run_knime_workflow.ps1` لأغراض التوثيق أو الدعم التاريخي، لكنه لم يعد مستخدماً في أي بيئة إنتاجية.

## 8. مكونات التحليلات البايثونية
- `backend/src/app/services/stage_07_analytics/impl.py`: المحرك الرئيسي ويستدعي المحركات الفرعية.
- `dq_engine.py`: 55 قاعدة لجودة البيانات → ينتج `outputs/dq_summary.json` والذي يحوِّله bridge إلى `profile/dq_report.json`.
- `clustering_engine.py`: يقيس التجمعات → `outputs/cluster_summary.json`.
- `anomaly_engine.py`: Isolation Forest → `outputs/anomalies.json`.
- `correlation_engine.py`: Pearson correlations → `outputs/correlation_matrix.json`.
- `forecast_engine.py`: متوسط متحرك بسيط → `outputs/forecast.parquet` + `forecast_summary.json`.
- `stage_07_knime_bridge` ينسخ هذه الملفات إلى `phase_07_knime/{outputs,transforms}` ويولّد `insights_fdr.json`, `dq_coverage_summary.json`, و`run_summary.md` ليستهلكها `/api/bi`.

## 9. مخرجات التحليلات المتقدمة
- وثيقة `docs/KNIME_ADVANCED_ANALYTICS.md` باتت مرجعاً للمحركات البايثونية الجديدة.
- في حالة غياب الملفات، يقوم `/api/bi` بإظهار ملخصات فارغة، لكن لا يلزم أي تشغيل خارجي أو اعتماد على KNIME.

## 10. الاختبارات وضمان الجودة
- الاختبار `tests/test_stage07_knime_bridge.py:17` يتأكد من إنتاج `layer2_candidate.json` وربطه بمخرجات Stage 07_5.
- يُنصح بإضافة اختبارات Snapshot لكل ملف يتم توليده من KNIME للتحقق من استقرار المخطط:
  ```bash
  pytest tests/test_stage07_knime_bridge.py
  ```
- يمكن محاكاة التشغيل الكامل عن طريق إنشاء مجلد artifacts محليًا ثم تشغيل السكربت batch للتحقق من المخرجات.

## 11. قائمة مرجعية للتسليم
- [ ] ضبط `bi_prep_mode` أو `MINDQ_BI_PREP_MODE` لتعطيل المرحلة فقط عندما يكون الهدف هو التخطي الصريح.
- [ ] التأكد من توفر schema وkpi_map في القنوات الأساسية أو إعداد fallback.
- [ ] مراجعة ملفات Stage 07_5 لضمان اكتمال `layer2_candidate`.
- [ ] الاحتفاظ بسجلات `bridge_summary.json` ضمن artefacts لمراجعة سريعة خلال التحقيقات.

## 12. مراجع إضافية
- الكود الرئيسي: `src/app/services/stage_07_bi_prep_python/impl.py` (مع alias قديم `stage_07_knime_bridge`).
- السكربتات: `knime/run_knime_workflow.ps1`, `scripts/knime_approval.ps1`.
- الوثائق الداعمة: `knime/README_QUICKSTART.md`, `docs/KNIME_ADVANCED_ANALYTICS.md`, `docs/PHASES_DETAILED_GUIDE.md`.
