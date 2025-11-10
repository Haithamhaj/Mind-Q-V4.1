# دليل التكامل الكامل لـ KNIME في Mind-Q V4.1

**آخر تحديث:** 4 نوفمبر 2025  
**الغرض:** توثيق كامل لكيفية تشغيل KNIME وتكاملها مع خط المعالجة

---

## 🎯 نظرة عامة

**KNIME** هي طبقة تحليلات اختيارية (Stage 07.B) تعمل **فوق** مخرجات Stage 07 لتوفير:
- **تحليلات جودة البيانات** (55 قاعدة DQ)
- **التجزئة والكلسترينج** (K-Means Clustering)
- **كشف الشذوذ** (Isolation Forest)
- **الارتباطات المتقدمة** (Correlation Matrix)
- **التنبؤات الزمنية** (Tree Ensemble Forecasting)

### ⚠️ **نقطة مهمة جداً:**
KNIME **ليست إلزامية** في خط المعالجة! إذا لم يتم تشغيلها:
- يستمر خط المعالجة بشكل طبيعي
- Stage 08 تستخدم **fallback** تلقائي لتوليد تحليلات أساسية
- BI Dashboard يعرض البيانات الأساسية بدون التحليلات المتقدمة

---

## 📋 التدفق الحالي للمعالجة

```
Stage 06 (Feature Engineering)
         ↓
    features.parquet
         ↓
Stage 07 (Readiness Gate)
         ↓
    readiness_report.json
    decision_manifest.json
    feature_report.json
         ↓
┌────────────────────────────────┐
│  Stage 07.B :: KNIME Bridge    │ ← اختياري (Prompt/Auto/Skip)
│  (يحضّر المدخلات لـ KNIME)      │
└────────────────────────────────┘
         ↓
    phase_07_knime/
         ├── data.parquet         ← نسخة من features
         ├── schema.json          ← من Stage 03
         ├── kpi_map.yml          ← من contracts/
         ├── run_meta.json        ← معلومات التشغيل
         └── profile/
             ├── readiness_report.json
             ├── decision_manifest.json
             ├── feature_report.json
             ├── bridge_summary.json
             └── layer2_candidate.json ← من Stage 07.5
         ↓
┌────────────────────────────────┐
│   KNIME Workflow (يدوي/batch)  │ ← يتطلب تشغيل يدوي!
│   knime/phase07_feature_app    │
└────────────────────────────────┘
         ↓
    phase_07_knime/outputs/      ← مخرجات KNIME
         ├── dq_summary.json
         ├── cluster_summary.json
         ├── cluster_assignments.parquet
         ├── anomalies.json
         ├── correlation_matrix.json
         └── forecast.parquet
         ↓
Stage 08 (Insights)
         ↓
    operational_insights.json
```

---

## 🔧 التكامل الحالي (Stage 07.B :: KNIME Bridge)

### الموقع في الكود
- **Implementation:** `src/app/services/stage_07_knime_bridge/impl.py`
- **API Endpoint:** `POST /v1/runs/{run_id}/phases/07/knime-bridge`
- **Pipeline Integration:** داخل `/v1/runs/{run_id}/execute-all`

### وضع التشغيل (3 خيارات)

يتم التحكم عبر `MINDQ_KNIME_MODE` أو `config.mode`:

#### 1. **Prompt Mode** (الافتراضي)
```bash
# لا يوجد متغير بيئة
python -m src.app.services.pipeline_api
```
**السلوك:**
- عند الوصول لـ Stage 07، يظهر prompt في الـ console:
  ```
  [Stage 07 :: KNIME Bridge] Run 'run-latest' is ready for KNIME preparation.
  Do you want to prepare artifacts for KNIME now?
    [Y]es  -> generate phase_07_knime inputs
    [N]o   -> skip for this run
  Your choice [y/N]:
  ```
- إذا كتبت `y`: ينشئ `phase_07_knime/` ويستمر
- إذا كتبت `n` أو Enter: يتخطى KNIME ويستمر مباشرة لـ Stage 08

#### 2. **Auto Mode** (موافقة تلقائية)
```bash
$env:MINDQ_KNIME_MODE = "auto"
python -m src.app.services.pipeline_api
```
**السلوك:**
- يتخطى الـ prompt تماماً
- ينشئ `phase_07_knime/` تلقائياً
- مثالي للتطوير والاختبار

#### 3. **Skip Mode** (تعطيل تام)
```bash
$env:MINDQ_KNIME_MODE = "skip"
python -m src.app.services.pipeline_api
```
**السلوك:**
- لا ينشئ `phase_07_knime/` على الإطلاق
- يتخطى Stage 07.B بالكامل
- Stage 08 تستخدم fallback تلقائياً

### ما الذي ينشئه Stage 07.B؟

عند الموافقة، يتم إنشاء:

```
artifacts/{run_id}/phase_07_knime/
├── data.parquet           ← نسخة من stage_06_features/features.parquet
├── schema.json            ← من stage_03_schema/schema_v1.json
├── kpi_map.yml            ← من backend/contracts/kpis.yml
├── run_meta.json          ← معلومات التشغيل + Git SHA + Timestamp
└── profile/
    ├── readiness_report.json      ← من stage_07_readiness/
    ├── decision_manifest.json     ← من stage_07_readiness/
    ├── feature_report.json        ← من stage_07_5_feature_report/
    ├── bridge_summary.json        ← ملخص عملية النسخ
    └── layer2_candidate.json      ← من stage_07_5/ (Variance + Comparative + Heatmap)
```

**ملف `run_meta.json` يحتوي:**
```json
{
  "run_id": "run-latest",
  "created_at": "2025-11-04T10:30:45.123Z",
  "workflow": "phase07_feature_app.knwf",
  "git_sha": "5e4cc1b...",
  "git_branch": "port/update-2025-10-11",
  "prompt": {
    "mode": "auto",
    "approved": true,
    "timestamp": "2025-11-04T10:30:45.123Z"
  },
  "inputs": {
    "features_source": "artifacts/run-latest/stage_06_features/features.parquet",
    "schema_source": "artifacts/run-latest/stage_03_schema/schema_v1.json",
    "kpi_source": "backend/contracts/kpis.yml"
  },
  "artifacts": {
    "data": "artifacts/run-latest/phase_07_knime/data.parquet",
    "schema": "artifacts/run-latest/phase_07_knime/schema.json",
    "kpi_map": "artifacts/run-latest/phase_07_knime/kpi_map.yml"
  },
  "gate": {
    "pass": true,
    "confidence": 0.85,
    "flags": []
  },
  "key_stats": {
    "total_rows": 125000,
    "total_columns": 45,
    "numeric_features": 28,
    "categorical_features": 17
  }
}
```

---

## 🚀 تشغيل KNIME Workflow (يدوي)

### الطريقة 1: من داخل KNIME GUI

#### الخطوة 1: تحضير البيئة
```powershell
# تفعيل موافقة KNIME التلقائية (مرة واحدة لكل session)
pwsh -File scripts/knime_approval.ps1 -ApprovalCount 1
```

#### الخطوة 2: فتح KNIME
```powershell
# إذا كان KNIME_HOME معرّف
& "$env:KNIME_HOME\knime.exe"

# أو مباشرة
& "C:\Program Files\KNIME\knime.exe"
```

#### الخطوة 3: استيراد Workflow
1. File → Import KNIME Workflow
2. Browse → اختر `C:\Github - MindQ\Mind-Q-V4.1\knime\phase07_feature_app.knwf`
3. OK

#### الخطوة 4: ضبط Flow Variables
في نافذة KNIME:
1. افتح Workflow Settings (أيقونة الترس)
2. Flow Variables:
   - `input_dir` = `C:\Github - MindQ\Mind-Q-V4.1\artifacts\run-latest\phase_07_knime`
   - `output_dir` = `C:\Github - MindQ\Mind-Q-V4.1\artifacts\run-latest\phase_07_knime\outputs`

#### الخطوة 5: تشغيل
- Run → Execute All Executable Nodes
- انتظر حتى تتحول جميع العقد للأخضر ✅

#### الخطوة 6: تحقق من المخرجات
```powershell
ls artifacts\run-latest\phase_07_knime\outputs\
# يجب أن ترى:
# - dq_summary.json
# - cluster_summary.json
# - features_validated.parquet
```

---

### الطريقة 2: تشغيل Batch من PowerShell

```powershell
# الخيار الأبسط (يستخدم run-latest)
pwsh -File knime/run_knime_workflow.ps1 `
    -RunId "run-latest" `
    -AutoApprove

# تشغيل متقدم (run محدد)
pwsh -File knime/run_knime_workflow.ps1 `
    -RunId "stage_08_run-20251101092802" `
    -Workflow "phase07_feature_app" `
    -AutoApprove

# تشغيل workflow مختلف (مستقبلاً)
pwsh -File knime/run_knime_workflow.ps1 `
    -RunId "run-latest" `
    -Workflow "phase07_dq.knwf" `
    -AutoApprove
```

**معاملات السكربت:**
- `RunId` (إلزامي): اسم مجلد الـ run في artifacts/
- `Workflow` (اختياري): اسم ملف .knwf (افتراضي: phase07_feature_app)
- `ArtifactsRoot` (اختياري): مسار مخصص لـ artifacts (افتراضي: ./artifacts)
- `AutoApprove` (اختياري): تخطي approval prompt
- `RequireApproval` (اختياري): إجبار طلب الموافقة حتى لو كان Auto
- `ApprovalCount` (اختياري): عدد مرات التشغيل المسموح بها (-1 = غير محدود)

**ملاحظة:** السكربت يبحث عن:
1. `knime/phase07_feature_app.knwf`
2. `knime/workflows/phase07_feature_app.knwf`

---

## 🔄 التكامل مع Stage 08

### كيف تقرأ Stage 08 مخرجات KNIME؟

في `backend/src/app/services/stage_08_insights/impl.py`:

```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]):
    base = Path(config["artifacts_root"]) / run_id
    knime_profile_dir = base / "phase_07_knime" / "profile"
    
    # محاولة قراءة مخرجات KNIME
    knime_files = {
        "layer2_candidate": knime_profile_dir / "layer2_candidate.json",
        "readiness_report": knime_profile_dir / "readiness_report.json",
        "decision_manifest": knime_profile_dir / "decision_manifest.json",
        "feature_report": knime_profile_dir / "feature_report.json",
        "bridge_summary": knime_profile_dir / "bridge_summary.json",
    }
    
    # إذا لم توجد المخرجات، استخدم fallback
    for key, path in knime_files.items():
        if not path.exists():
            print(f"[Stage 08] KNIME file {key} not found, using fallback")
            # توليد تلقائي من data.parquet
```

### ملفات KNIME المتوقعة من قبل Stage 08

| الملف | الموقع | الغرض | Fallback |
|------|--------|-------|----------|
| `layer2_candidate.json` | `phase_07_knime/profile/` | بيانات Variance + Comparative + Heatmap من Stage 07.5 | ✅ من stage_07_5/ مباشرة |
| `readiness_report.json` | `phase_07_knime/profile/` | تقرير جاهزية البيانات | ✅ من stage_07_readiness/ |
| `cluster_summary.json` | `phase_07_knime/outputs/` | ملخص التجزئة | ✅ K-Means أساسي على data.parquet |
| `anomalies.json` | `phase_07_knime/outputs/` | الشذوذات المكتشفة | ✅ Isolation Forest أساسي |
| `correlation_matrix.json` | `phase_07_knime/outputs/` | مصفوفة الارتباطات | ✅ حساب Pearson مباشر |
| `forecast.parquet` | `phase_07_knime/outputs/` | التنبؤات الزمنية | ✅ متوسط متحرك بسيط |

---

## 🎨 Workflows المتاحة حالياً

### 1. **phase07_feature_app.knwf** (الحالي)

**الوظيفة:** Workflow أساسي للتحقق من البيانات وإعدادها

**المكونات:**
- **Input Loader (#1)**: قراءة `data.parquet` من `${input_dir}`
- **DQ Validator (#2)**: فحوصات جودة بيانات أساسية (NULL، Duplicates، Outliers)
- **Output Writer (#3)**: كتابة `features_validated.parquet` لـ `${output_dir}`

**المخرجات:**
- `outputs/features_validated.parquet`

**الحالة:** ✅ جاهز للاستخدام (تجريبي)

---

### 2. **phase07_dq.knwf** (مخطط - غير موجود)

**الوظيفة:** تطبيق 55 قاعدة DQ الكاملة

**المخرجات المتوقعة:**
- `outputs/dq_summary.json`
- `outputs/dq_failures.parquet`

**الحالة:** 📋 مخطط (انظر `docs/KNIME_STRATEGY_PLAN.md`)

---

### 3. **phase07_clustering.knwf** (مخطط - غير موجود)

**الوظيفة:** تجزئة العملاء/الشحنات

**المخرجات المتوقعة:**
- `outputs/cluster_summary.json`
- `outputs/cluster_assignments.parquet`

**الحالة:** 📋 مخطط

---

### 4. **phase07_forecasting.knwf** (مخطط - غير موجود)

**الوظيفة:** توقعات الطلب

**المخرجات المتوقعة:**
- `outputs/forecast.parquet`
- `models/tree_ensemble.pmml`

**الحالة:** 📋 مخطط

---

### 5. **phase07_anomalies.knwf** (مخطط - غير موجود)

**الوظيفة:** كشف الشذوذ في العمليات

**المخرجات المتوقعة:**
- `outputs/anomalies.json`

**الحالة:** 📋 مخطط

---

## 🛠️ خطوات التكامل اليدوي المطلوبة

### ✅ ما تم تنفيذه

1. **Stage 07.B KNIME Bridge** - جاهز ومدمج في Pipeline
2. **Prompt System** - يعمل (Auto/Prompt/Skip)
3. **Data Preparation** - ينسخ features + schema + kpis تلقائياً
4. **PowerShell Runner** - `knime/run_knime_workflow.ps1` جاهز
5. **Fallback Mechanism** - Stage 08 تستطيع العمل بدون KNIME
6. **API Endpoint** - `POST /v1/runs/{run_id}/phases/07/knime-bridge`

### ⚠️ ما يحتاج تدخل يدوي

#### 1. **تشغيل KNIME Workflow يدوياً**
**السبب:** لا يوجد KNIME Server، التشغيل batch يتطلب تفاعل

**الحلول المتاحة:**

##### الحل A: تشغيل يدوي بعد كل Pipeline Run
```powershell
# 1. شغّل Pipeline بالكامل
curl -X POST http://localhost:8000/v1/runs/run-latest/execute-all

# 2. انتظر حتى ينتهي Stage 07

# 3. شغّل KNIME يدوياً
pwsh -File knime/run_knime_workflow.ps1 -RunId "run-latest" -AutoApprove

# 4. استكمل Pipeline (إذا لزم)
# Stage 08 ستقرأ المخرجات تلقائياً
```

##### الحل B: Pipeline متقطع (مع توقف بعد Stage 07)
```python
# تعديل في pipeline_api/app.py
MANUAL_STAGES = ["07_knime_bridge"]

# عند الوصول لـ KNIME، توقف مؤقت:
if phase_key in MANUAL_STAGES:
    return {
        "status": "WAITING_MANUAL",
        "message": "Please run KNIME workflow manually",
        "command": f"pwsh -File knime/run_knime_workflow.ps1 -RunId {run_id}"
    }
```

##### الحل C: Task Scheduler (Windows)
```powershell
# إنشاء Scheduled Task تراقب phase_07_knime/
$trigger = New-JobTrigger -Once -At (Get-Date) -RepeatInterval (New-TimeSpan -Minutes 5)
$action = { 
    $dir = "C:\Github - MindQ\Mind-Q-V4.1\artifacts\run-latest\phase_07_knime"
    if (Test-Path "$dir\run_meta.json") {
        & pwsh -File knime/run_knime_workflow.ps1 -RunId "run-latest" -AutoApprove
    }
}
Register-ScheduledJob -Name "KNIME Auto Runner" -Trigger $trigger -ScriptBlock $action
```

#### 2. **بناء Workflows الإضافية**
**الحالي:** فقط `phase07_feature_app.knwf` موجود

**المطلوب:** (حسب `KNIME_STRATEGY_PLAN.md`)
- [ ] `phase07_dq.knwf` - 55 قاعدة DQ
- [ ] `phase07_clustering.knwf` - K-Means + تقسيم
- [ ] `phase07_forecasting.knwf` - Tree Ensemble
- [ ] `phase07_anomalies.knwf` - Isolation Forest
- [ ] `phase07_correlations.knwf` - ارتباطات متقدمة

**خطوات البناء:**
1. افتح KNIME Desktop
2. File → New KNIME Workflow
3. أضف العقد المطلوبة:
   - Parquet Reader (من `${input_dir}/data.parquet`)
   - Python Script Node (من `scripts/knime_py/`)
   - K-Means / Tree Ensemble / Isolation Forest
   - JSON Writer (لـ `${output_dir}/`)
4. احفظ في `knime/workflows/`
5. اختبر عبر `run_knime_workflow.ps1 -Workflow "phase07_dq"`

#### 3. **ربط Python Scripts بـ KNIME**
**الحالي:** مكتبة `scripts/knime_py/` موجودة لكن غير مستخدمة في Workflows

**الملفات المتاحة:**
- `dq_rules.py` - تطبيق قواعد DQ
- `json_utils.py` - تحويل DataFrames → JSON
- `feature_engineering.py` - معالجة ميزات

**خطوات الربط:**
1. افتح KNIME Preferences → Python
2. حدد Python Environment:
   ```
   C:\Github - MindQ\Mind-Q-V4.1\.venv\Scripts\python.exe
   ```
3. في Workflow، أضف Python Script Node
4. استورد:
   ```python
   import sys
   sys.path.append('C:/Github - MindQ/Mind-Q-V4.1/scripts')
   from knime_py import dq_rules, json_utils
   
   # استخدم الدوال
   results = dq_rules.apply_all_rules(input_table_1)
   json_utils.write_json_file(results, output_path)
   ```

#### 4. **إعداد Python Environment لـ KNIME**
**الحالي:** يستخدم Python عام من النظام

**المطلوب:** بيئة مخصصة مع جميع المكتبات

```powershell
# إنشاء بيئة KNIME مخصصة
python -m venv tools/knime/python_env

# تفعيل
tools/knime/python_env/Scripts/Activate.ps1

# تثبيت المكتبات
pip install numpy pandas polars pyarrow scikit-learn

# ربط بـ KNIME
# File → Preferences → KNIME → Python
# Python 3 → Browse → tools/knime/python_env/Scripts/python.exe
```

---

## 📊 مثال سيناريو كامل

### السيناريو: تشغيل Pipeline كامل مع KNIME

```powershell
# 1. ضبط البيئة للموافقة التلقائية على KNIME
$env:MINDQ_KNIME_MODE = "auto"

# 2. تشغيل Backend
cd "C:\Github - MindQ\Mind-Q-V4.1"
python -m src.app.services.pipeline_api

# 3. في terminal آخر، شغّل Pipeline
curl -X POST http://localhost:8000/v1/runs/run-latest/execute-all `
  -H "Content-Type: application/json" `
  -d '{}'

# 4. انتظر حتى ينتهي Pipeline (مراقبة logs)
# سترى:
# [Stage 07 :: KNIME Bridge] Auto-approved, preparing phase_07_knime/

# 5. بعد Stage 07، شغّل KNIME يدوياً
pwsh -File knime/run_knime_workflow.ps1 `
    -RunId "run-latest" `
    -AutoApprove

# 6. تحقق من المخرجات
ls artifacts/run-latest/phase_07_knime/outputs/

# 7. Stage 08 ستقرأ النتائج تلقائياً
curl http://localhost:8000/v1/runs/run-latest/bi-intelligence | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

---

## 🧪 اختبار التكامل

### اختبار 1: هل Stage 07.B تعمل؟
```powershell
# شغّل Pipeline بـ prompt mode
$env:MINDQ_KNIME_MODE = "prompt"
curl -X POST http://localhost:8000/v1/runs/test-knime/execute-all

# اضغط 'y' عندما يُطلب منك
# تحقق من النتيجة
ls artifacts/test-knime/phase_07_knime/
# يجب أن ترى: data.parquet, schema.json, run_meta.json, profile/
```

### اختبار 2: هل KNIME Workflow يشتغل؟
```powershell
# تحضير بيانات تجريبية
mkdir -Force artifacts/test-knime/phase_07_knime
Copy-Item artifacts/run-latest/stage_06_features/features.parquet `
          artifacts/test-knime/phase_07_knime/data.parquet

# تشغيل KNIME
pwsh -File knime/run_knime_workflow.ps1 -RunId "test-knime" -AutoApprove

# تحقق
ls artifacts/test-knime/phase_07_knime/outputs/
```

### اختبار 3: هل Fallback يعمل؟
```powershell
# شغّل Pipeline بدون KNIME
$env:MINDQ_KNIME_MODE = "skip"
curl -X POST http://localhost:8000/v1/runs/test-fallback/execute-all

# Stage 08 يجب أن تستخدم fallback تلقائياً
curl http://localhost:8000/v1/runs/test-fallback/bi-intelligence

# ابحث عن "fallback" في الـ response
```

---

## 🔍 استكشاف الأخطاء

### المشكلة: "KNIME executable not found"
**السبب:** `KNIME_HOME` غير معرّف أو خاطئ

**الحل:**
```powershell
# 1. ابحث عن KNIME
dir "C:\Program Files\KNIME" -Recurse | Where-Object { $_.Name -eq "knime.exe" }

# 2. اضبط المتغير
$env:KNIME_HOME = "C:\Program Files\KNIME"

# أو
$env:KNIME_HOME = "C:\Github - MindQ\Mind-Q-V4.1\tools\knime\knime_5.5.1"
```

### المشكلة: "Input directory not found"
**السبب:** `phase_07_knime/` لم يُنشأ

**الحل:**
```powershell
# تأكد من تشغيل Stage 07.B أولاً
curl -X POST http://localhost:8000/v1/runs/run-latest/phases/07/knime-bridge `
  -H "Content-Type: application/json" `
  -d '{"config": {"mode": "auto"}}'

# أو يدوياً
mkdir -Force artifacts/run-latest/phase_07_knime
Copy-Item artifacts/run-latest/stage_06_features/features.parquet `
          artifacts/run-latest/phase_07_knime/data.parquet
```

### المشكلة: Workflow لا يعمل في GUI
**السبب:** Flow Variables غير مضبوطة

**الحل:**
1. افتح Workflow Settings (أيقونة الترس)
2. Flow Variables → Add:
   - Name: `input_dir`, Type: String, Value: مسار كامل
   - Name: `output_dir`, Type: String, Value: مسار كامل
3. Reset → Execute All

### المشكلة: Python Script Node فشل
**السبب:** Python environment غير مربوط

**الحل:**
1. File → Preferences → KNIME → Python
2. Python 3 → Browse → اختر `.venv\Scripts\python.exe`
3. Apply → OK
4. Reset Workflow → Execute

---

## 📝 ملخص الخطوات اليدوية المطلوبة

### لكل Pipeline Run:

#### **إذا كنت تريد استخدام KNIME:**
1. ✅ شغّل Pipeline مع `MINDQ_KNIME_MODE=auto`
2. ✅ انتظر حتى Stage 07 تنتهي
3. ⚠️ **شغّل KNIME يدوياً:**
   ```powershell
   pwsh -File knime/run_knime_workflow.ps1 -RunId "run-latest" -AutoApprove
   ```
4. ✅ استكمل Pipeline (Stage 08 ستقرأ النتائج)

#### **إذا كنت لا تريد استخدام KNIME:**
1. ✅ شغّل Pipeline مع `MINDQ_KNIME_MODE=skip`
2. ✅ كل شيء سيعمل تلقائياً مع fallback

---

## 🚧 التطوير المستقبلي

### خيارات الأتمتة الكاملة:

1. **KNIME Server** (مدفوع)
   - يتيح REST API لتشغيل Workflows
   - تكامل كامل داخل Pipeline
   - تكلفة: $$$

2. **Python Integration** (بديل مجاني)
   - إعادة كتابة KNIME workflows كـ Python scripts
   - استخدام `knime_py/` مباشرة
   - التكامل: استبدال `run_knime_workflow.ps1` بـ `python scripts/run_knime_python.py`

3. **File Watcher Service** (حل وسط)
   - خدمة Windows تراقب `phase_07_knime/run_meta.json`
   - تشغيل KNIME تلقائياً عند اكتشاف ملف جديد
   - لا يتطلب تغييرات في Backend

### الخيار المُوصى به: **Python Integration**

**المميزات:**
- ✅ لا يحتاج KNIME Desktop/Server
- ✅ تكامل كامل مع Pipeline
- ✅ أسرع في التنفيذ
- ✅ يعمل في Replit/Docker

**الخطوات:**
1. نقل منطق DQ من KNIME → `scripts/knime_py/dq_rules.py`
2. نقل K-Means → `scripts/knime_py/clustering.py`
3. نقل Isolation Forest → `scripts/knime_py/anomaly_detection.py`
4. إنشاء `backend/src/app/services/stage_07_analytics/impl.py`
5. استبدال `stage_07_knime_bridge` → `stage_07_analytics`

**الجدول الزمني:** 2-3 أسابيع

---

## 📚 مراجع إضافية

- **KNIME Strategy Plan:** `docs/KNIME_STRATEGY_PLAN.md`
- **KNIME Advanced Analytics:** `docs/KNIME_ADVANCED_ANALYTICS.md`
- **KNIME Quick Start:** `knime/README_QUICKSTART.md`
- **Stage 08 Analysis:** `docs/STAGE_08_INSIGHTS_ANALYSIS.md`
- **Pipeline API:** `docs/PIPELINE_API.md`

---

## 🎓 الخلاصة

**KNIME حالياً:**
- ✅ متكاملة في Pipeline (Stage 07.B)
- ✅ Prompt System يعمل
- ✅ Fallback جاهز
- ⚠️ **يحتاج تشغيل يدوي لـ Workflows**

**للاستخدام الفوري:**
```powershell
# 1. ضبط auto mode
$env:MINDQ_KNIME_MODE = "auto"

# 2. شغّل Pipeline
curl -X POST http://localhost:8000/v1/runs/run-latest/execute-all

# 3. بعد Stage 07، شغّل KNIME
pwsh -File knime/run_knime_workflow.ps1 -RunId "run-latest" -AutoApprove
```

**للإنتاج:** يُنصح بـ **Python Integration** بدلاً من KNIME لتحقيق أتمتة كاملة.
