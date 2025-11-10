# وثيقة التكامل مع KNIME (Stage 07 Bridge)

## 1. الهدف والنطاق
- شرح كيفية تجهيز المرحلة 07 لمدّ KNIME بالمدخلات القياسية وقراءة المخرجات.
- توثيق خيارات التشغيل (Prompt/Auto/Skip) ومسار الموافقات والسكربتات المساندة.
- تغطية الاعتمادات بين المراحل (Stage 06، Stage 07.5، Stage 08) وما ينتج عنها من ملفات.

## 2. نظرة سريعة على التدفق
1. مرحلة Stage 06 تنشر ملف الميزات `features.parquet`.
2. مرحلة Stage 07_5 تنتج ملفات تحليل إضافية (`variance_analysis.json`, `comparative_summary.json`, `heatmap_matrix.json`).
3. عند استدعاء `stage_07_knime_bridge.run` يتم تحديد وضع التشغيل ثم تجهيز مجلد `artifacts/<run_id>/phase_07_knime/`.
4. يتم نسخ البيانات، السكيمة، خريطة الـ KPI، تقارير الجاهزية، وملف `run_meta.json` إلى مجلد KNIME.
5. يتم إنتاج `layer2_candidate.json` و`bridge_summary.json` ونسخها أيضًا إلى `artifacts/<run_id>/stage_07_knime_bridge/profile/` لاحتياجات الـ API.
6. عند تفعيل تشغيل batch، يتم استدعاء سكربت KNIME مع تحديد الـ workflow المطلوب.

## 3. ضبط وضعية التشغيل
- الدالة `_resolve_mode` تقرأ المفاتيح `mode` أو `knime_mode` من التهيئة، ثم القيم البيئية `MINDQ_KNIME_MODE` أو `KNIME_PIPELINE_MODE`، مع دعم الأعلام `auto_approve` و`auto_skip` (`src/app/services/stage_07_knime_bridge/impl.py:30`).
- القيم الممكنة: `auto` (تشغيل بدون تفاعل)، `prompt` (الافتراضية مع استدعاء `_prompt_user`)، `skip` (يتجاهل التحضير ويعيد حالة SKIP).
- `_prompt_user` يعرض رسالة تفاعلية في حال توفر TTY، وإلا يفترض الرفض الآمن (`impl.py:52`).

## 4. الملفات التي يتم تجهيزها
- `phase_07_knime/data.parquet`: نسخة من Stage 06.
- `phase_07_knime/schema.json`: يتم البحث عنها حسب الأولوية (Stage 03، ثم `contracts/schema.json`).
- `phase_07_knime/kpi_map.yml`: من Stage 06 أو fallback إلى `backend/contracts/kpis.yml`.
- `phase_07_knime/profile/`: يحتوي نسخًا من `readiness_report.json`, `decision_manifest.json`, `feature_report.json` إن وجدت.
- `phase_07_knime/outputs/` (اختياري): ملفات التحليلات المتقدمة مثل `cluster_summary.json`, `anomalies.json`, `correlation_matrix.json`, و`orders_forecast*.parquet` ليتم استهلاكها في Stage 08 (مع fallback تلقائي عند الغياب).
- `phase_07_knime/run_meta.json`: يتضمن `run_id`, `workflow`, `git_sha`, `git_branch`, مصادر الملفات، وملخص جودة البيانات (`impl.py:198`).
- `phase_07_knime/profile/bridge_summary.json`: يلخص ما تم نسخه مع التوقيت والوضع (`impl.py:223`).
- `layer2_candidate.json`: يُبنى من مخرجات Stage 07_5 أو يتم إنشاء قالب فارغ مع ملاحظة غياب البيانات (`impl.py:107`).
- يتم نسخ `bridge_summary.json`, `layer2_candidate.json`, `feature_report.json` إلى `stage_07_knime_bridge/profile/` لضمان التناسق مع طبقات BI.

## 5. خيارات التشغيل المتقدمة
- `run_batch`: يشغّل KNIME batch بعد تجهيز الملفات.
- `only_execute`: يتخطّى التحضير ويفترض أن الملفات جاهزة ثم يشغّل batch.
- `auto_execute`: عند قيمته True مع وضعية auto يتم تشغيل batch تلقائيًا.
- النتيجة النهائية تتضمن حقل `metrics` مع `prepared_files`, `mode`, وكود الخروج من KNIME إذا تم التشغيل (`impl.py:268`).

## 6. بوابة الموافقات
- سكربت `scripts/knime_approval.ps1` يوفر الدالة `Confirm-KnimeApproval` لإنفاذ الموافقات أو تخزين رصيد تشغيلات مسبقة (`scripts/knime_approval.ps1:1`).
- يدعم المتغيرات البيئية `KNIME_REQUIRE_APPROVAL`, `KNIME_APPROVAL_COUNT`, والـ switch `-AutoApprove` في حال دمجه مع CI.
- يسجل الرصيد في `tools/knime/.approval_state.json` حتى يتم استهلاكه.

## 7. تشغيل KNIME Batch
- السكربت `knime/run_knime_workflow.ps1` يدعم المعلمات الجديدة:
  - `-Workflow <name|path>` لاختيار أي workflow (يُضاف `.knwf` تلقائيًا عند الحاجة).
  - `-ArtifactsRoot <path>` لتخصيص مصدر المجلدات تجاه سيناريوهات اختبارية.
  - `-OutputSubdir <name>` لعزل مخرجات workflow داخل مجلد فرعي (مثل `outputs/forecasting`).
  - `-DisableGitSuffix` لتعطيل إنشاء مجلد `git_<sha>` عند الرغبة.
- مثال تشغيل مباشر:
  ```pwsh
  pwsh -File knime/run_knime_workflow.ps1 -RunId <run_id> -Workflow phase07_dq -OutputSubdir outputs\dq -AutoApprove
  ```
- عند توفر `git_sha` في `run_meta.json` يتم إنشاء مجلد فرعي `git_<sha>` داخل `phase_07_knime` لتجميع المخرجات، ما لم يتم تمرير `-DisableGitSuffix`.
- المتغيرات الأساسية الممررة إلى الـ workflow: `input_dir` و`output_dir`, مع تفعيل `-reset` لضمان نظافة الحالة (`knime/run_knime_workflow.ps1`).

## 8. مكونات Workflow داخل KNIME
- `node_1`: قارئ Parquet يحمّل `${input_dir}/data.parquet` (`knime/phase07_feature_app/node_1/settings.xml`).
- `node_2`: عقدة Python Script (knime.python3) تحتوي منطق التحقق من الجودة (قابل للتعديل لاستدعاء `scripts/knime_py/dq_rules.py`).
- `node_3`: كاتب Parquet يصدّر `features_validated.parquet` إلى `${output_dir}` (`node_3/settings.xml`).
- `node_4`: Table View لعرض البيانات داخل KNIME GUI (`node_4/settings.xml`).
- يمكن تعديل عقدة Python لاستدعاء الدوال المشتركة من `scripts/knime_py/` للحفاظ على تناسق المنطق مع backend.

## 9. مخرجات التحليلات المتقدمة
- وثيقة `docs/KNIME_ADVANCED_ANALYTICS.md` تفصّل كيف يكمّل KNIME التحليلات المتقدمة (Clusters, Anomalies, Correlations, Forecast).
- في حالة غياب هذه الملفات، يقوم backend بتوليد fallback اعتمادًا على `phase_07_knime/data.parquet` لضمان استمرار العرض في BI.

## 10. الاختبارات وضمان الجودة
- الاختبار `tests/test_stage07_knime_bridge.py:17` يتأكد من إنتاج `layer2_candidate.json` وربطه بمخرجات Stage 07_5.
- يُنصح بإضافة اختبارات Snapshot لكل ملف يتم توليده من KNIME للتحقق من استقرار المخطط:
  ```bash
  pytest tests/test_stage07_knime_bridge.py
  ```
- يمكن محاكاة التشغيل الكامل عن طريق إنشاء مجلد artifacts محليًا ثم تشغيل السكربت batch للتحقق من المخرجات.

## 11. قائمة مرجعية للتسليم
- [ ] ضبط `mode` أو `MINDQ_KNIME_MODE` حسب سيناريو التشغيل (Local vs CI).
- [ ] التأكد من توفر schema وkpi_map في القنوات الأساسية أو إعداد fallback.
- [ ] مراجعة ملفات Stage 07_5 لضمان اكتمال `layer2_candidate`.
- [ ] تفعيل `run_batch`/`auto_execute` فقط في البيئات التي يتوفر فيها `knime.exe`.
- [ ] الاحتفاظ بسجلات `bridge_summary.json` ضمن artefacts لمراجعة سريعة خلال التحقيقات.

## 12. مراجع إضافية
- الكود الرئيسي: `src/app/services/stage_07_knime_bridge/impl.py`.
- السكربتات: `knime/run_knime_workflow.ps1`, `scripts/knime_approval.ps1`.
- الوثائق الداعمة: `knime/README_QUICKSTART.md`, `docs/KNIME_ADVANCED_ANALYTICS.md`, `docs/PHASES_DETAILED_GUIDE.md`.
### Safety toggle: enable_knime_stub

Set `enable_knime_stub=true` (or export `MINDQ_ENABLE_KNIME_STUB=1`) only when you explicitly want the bridge to synthesize placeholder `analytics_summary.json`. The default is `false`, preventing accidental stub artifacts from leaking into Stage 08/09 when production analytics should be the only source of truth.
