# خطة تطوير طبقة KNIME

## 1. الرؤية والهدف
- بناء طبقة تحليلات منفصلة (Stage 07.B) فوق مخرجات Stage 07 لضمان الاستفادة القصوى من KNIME Desktop المجاني دون التأثير على خط معالجة البيانات الأساسي.
- تمكين الفريق من تقديم تحليلات متقدمة (DQ، كلسترينج، توقعات شجرية، كشف الشذوذ) وإرجاع مخرجات قياسية يمكن استهلاكها مباشرة من Stage 08 وBI.

## 2. نطاق العمل والاعتماديات
- المدخلات الرسمية: `artifacts/<run_id>/phase_07_knime/` التي يولدها Stage 07 Bridge وتتضمن `data.parquet`, `run_meta.json`, وملفات profile.
- المخرجات الرسمية: مسار موحد `artifacts/<run_id>/phase_07_knime/outputs/` بالإضافة إلى نسخ موجزة داخل `stage_07_knime_bridge/profile/` لضمان التوافق مع واجهات REST.
- الأدوات المتاحة في النسخة المجانية: KNIME Analytics Platform، عقد Python Script، H2O، تكامل scikit-learn، Flow Variables، Components.
- لا يوجد خادم KNIME؛ التشغيل يتم محليًا أو عبر PowerShell batch (`knime/run_knime_workflow.ps1`).

## 3. تصميم الطبقات والهيكل
```
artifacts/<run_id>/
  phase_07_knime/
    data.parquet
    schema.json
    profile/
      readiness_report.json
      decision_manifest.json
      feature_report.json
      bridge_summary.json
      layer2_candidate.json
    outputs/
      dq_summary.json
      cluster_summary.json
      cluster_assignments.parquet
      anomalies.json
      feature_importance.json
      forecast.parquet
    models/
      tree_ensemble.pmml
    logs/
      operations.log
```
- كل Workflow ينتج مخرجاته في مجلد فرعي واضح (`outputs/`، `models/`، `logs/`).
- Stage 07 Bridge يحتفظ بآلية fallback لأي ملف مفقود لضمان استقرار الخدمات.

## 4. حالات الاستخدام المحورية
| الحالة | الهدف | العقد الأساسية | المخرجات | الملاحظات |
|--------|-------|----------------|----------|-----------|
| DQ & Profiling | قياس جودة البيانات وتوثيق التباينات | Parquet Reader، Python Script، Rule Engine، JSON Writer | `dq_summary.json`, `dq_failures.parquet` | يتم دمج 55 قاعدة DQ المتفق عليها |
| Clustering & Segmentation | تقسيم العملاء/الشحنات إلى شرائح | Column Filter، K-Means، Cluster Assigner، Table Writer | `cluster_summary.json`, `cluster_assignments.parquet` | تحفظ المعايير (k، الميزات) داخل `run_meta.json` |
| Tree Ensemble Forecasting | توقع حجم الطلب أو الأداء | Partitioning، Tree Ensemble Learner/Predictor، PMML Writer | `forecast.parquet`, `models/tree_ensemble.pmml` | التدريب والتنبؤ في Workflows منفصلة |
| Anomaly Detection | اكتشاف حالات شاذة في العمليات | Isolation Forest، Math Formula، JSON Writer | `anomalies.json` | يسمح بضبط نسبة الشذوذ |
| Correlation & Feature Importance | دعم Stage 08 بالتحليلات | Linear Correlation، Feature Importance (Shapley)، Table Writer | `correlations.json`, `feature_importance.json` | تستخدم نصوص Python لتحويل الجداول إلى JSON |

## 5. تنظيم الـ Workflows
- إنشاء مجلد `knime/workflows/` يضم:
  - `phase07_prepare.knwf` (الإعداد الحالي).
  - `phase07_dq.knwf`.
  - `phase07_clustering.knwf`.
  - `phase07_forecasting.knwf`.
  - `phase07_anomalies.knwf`.
- كل Workflow يستخدم Flow Variables `input_dir` و`output_dir` التي يضخها السكربت.
- استخدام Components لتجميع العقد المشتركة (قراءة البيانات، كتابة المخرجات، تسجيل العمليات).
- إضافة عقدة Logger في بداية كل workflow لكتابة `logs/operations.log` باستخدام `String Manipulation` + `File Writer`.

## 6. تكامل Python داخل KNIME
- إعداد بيئة Python واحدة (`tools/knime/python_env/`) وتوثيق خطوات الربط من إعدادات KNIME.
- تم إنشاء مكتبة مشتركة `scripts/knime_py/` تحتوي وحدات مبدئية:
  - `dq_rules.py`: يطبق قواعد جودة أولية ويعيد ملخصًا قياسيًا.
  - `json_utils.py`: يوفر دوال `to_compact_json` و`write_json_file` لدمجها مع عقدة Python.
  - `feature_engineering.py`: يحضّر ميزات جاهزة للنمذجة (اختيار، One-Hot، تنظيف).
- يتم استيراد هذه الوحدات من `__init__.py` لتسهيل استخدامها داخل عقد KNIME Script، مع إمكانية توسعتها لاحقًا.

## 7. الأتمتة والحَوْكَمة
- السكربت `knime/run_knime_workflow.ps1` يدعم الآن المعلمات:
  - `-Workflow <name|path>` لاختيار أي Workflow (يتم إضافة `.knwf` تلقائيًا عند عدم تحديد الامتداد).
  - `-ArtifactsRoot <path>` لتجاوز مجلد `artifacts` الافتراضي.
  - `-OutputSubdir <name>` لإنشاء مسار فرعي خاص بمخرجات workflow.
  - `-DisableGitSuffix` لإلغاء إنشاء مجلد `git_<sha>` عند الحاجة.
- الاستمرار باستخدام `scripts/knime_approval.ps1` لضبط عدد التشغيلات المسموح بها وتفعيل الموافقة في البيئات الإنتاجية.
- تطوير سكربت إضافي `scripts/run_knime_suite.ps1` (لاحقًا) لتشغيل جميع الـ workflows بالتتابع وجمع الرموز المرجعية للأخطاء.
- اختبار النتائج عبر `pytest tests/test_stage07_knime_bridge.py` مع إضافة اختبارات snapshot لكل مخرجات KNIME الجديدة.
- توثيق حالة المخرجات في `bridge_summary.json` للإشارة إلى ما إذا كانت نتائج KNIME متاحة أو تم الاعتماد على fallback.

## 8. خارطة الطريق التنفيذية
1. **التهيئة (أسبوع 1)**
   - نشر نسخة السكربت الجديدة وتوثيق الاستخدام في README.
   - إنشاء وتضمين مكتبة `scripts/knime_py` داخل عقود Python.
2. **تحليلات الجودة (أسبوع 2)**
   - بناء `phase07_dq.knwf` وربطها بـ 55 قاعدة جودة البيانات.
   - إنتاج `dq_summary.json` وتحديث اختبار `test_stage07_knime_bridge.py`.
3. **التحليلات المتقدمة (أسبوع 3-4)**
   - تنفيذ Workflow للكلسترينج والتوثيق.
   - تنفيذ Workflow للتنبؤات الشجرية (training + scoring) وربط النموذج بـ `models/`.
   - إنشاء Workflow للكشف عن الشذوذ وإرجاع `anomalies.json`.
4. **الدمج والحوكمة (أسبوع 5)**
   - توحيد إخراجات JSON في Stage 07 Bridge وربطها بـ Stage 08.
   - إضافة اختبارات snapshot + سكربت `run_knime_suite.ps1`.
   - تحديث الوثائق (`docs/KNIME_BRIDGE_OVERVIEW.md`, `docs/KNIME_ADVANCED_ANALYTICS.md`).
5. **التطوير المستمر (بعد الإطلاق)**
   - تقييم الاستخدام وتحسين المعايير (عدد المجموعات، عتبات الشذوذ).
   - إضافة دعم لنماذج أخرى (XGBoost عبر Python Script) حسب الحاجة.

## 9. الموارد والتعلم
- دليل KNIME الرسمي (Desktop): https://docs.knime.com
- أمثلة H2O وTree Ensemble المتاحة ضمن KNIME Labs.
- وثائق المشروع الحالية: `docs/KNIME_BRIDGE_OVERVIEW.md`, `docs/KNIME_ADVANCED_ANALYTICS.md`.
- مسارات التدريب الداخلي: تسجيل جلسات توضيحية وحفظها في `docs/training/`.

## 10. قائمة التحقق للتسليم
- [ ] تحديث README وملفات التشغيل لشرح المعلمات الجديدة (`-Workflow`, `-OutputSubdir`).
- [ ] إنشاء workflows الجديدة داخل `knime/workflows/`.
- [ ] توسيع مكتبة Python بقواعد DQ الفعلية وربطها بالبيانات المرجعية.
- [ ] إنشاء مخرجات JSON/Parquet قياسية وربطها بـ Stage 08.
- [ ] إعداد اختبارات تلقائية ومراجعة السجلات داخل `bridge_summary.json`.
- [ ] تحديث الوثائق وإعلام الفريق بخطوات التشغيل.
