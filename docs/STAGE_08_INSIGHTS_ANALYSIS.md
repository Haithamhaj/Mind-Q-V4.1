# 📊 تحليل شامل للمرحلة 8 - Operational Insights

## 🎯 نظرة عامة

**المرحلة 8 (Stage 08 - Operational Insights)** هي مرحلة حاسمة في خط المعالجة تقوم بتحويل الارتباطات الإحصائية إلى رؤى تشغيلية قابلة للتنفيذ مع تقييم موثوقيتها.

---

## 📥 المدخلات (Inputs)

### 1️⃣ المدخلات الأساسية (Required)

| الملف | المصدر | الوصف |
|------|--------|-------|
| `features.parquet` | Stage 06 Feature Engineering | البيانات المعالجة مع الخصائص المهندسة |
| `correlations_kpi.json` أو `correlations.json` | Stage 07 Correlations | الارتباطات بين الخصائص والـ KPIs |
| `redundancy.json` | Stage 07 Correlations | تقييم التكرار بين الخصائص |

### 2️⃣ المدخلات الاختيارية (Optional)

| الملف | المصدر | الوصف |
|------|--------|-------|
| `text_profile.json` | Stage 03.5 TextOps | تحليل النصوص والعبارات الشائعة |
| `sentiment_features.parquet` | Stage 03.5 TextOps | خصائص المشاعر المستخرجة |
| `variance_analysis.json` | Stage 07.5 Feature Report | تحليل التباين (Layer 2) |
| `comparative_summary.json` | Stage 07.5 Feature Report | ملخص المقارنات (Layer 2) |
| `heatmap_matrix.json` | Stage 07.5 Feature Report | مصفوفة الارتباطات (Layer 2) |
| `layer2_candidate.json` | KNIME Profile | مرشحات Layer 2 |
| `cluster_summary.json` | KNIME Profile / Outputs | مخرجات التجميع المتقدمة |
| `anomalies.json` | KNIME Profile / Outputs | نتائج كشف الشذوذ المتقدمة |
| `correlation_matrix.json` | KNIME Profile / Outputs | مصفوفة ارتباط موسعة |
| `orders_forecast*.parquet` | KNIME Transforms / Outputs | تنبؤات الطلب القصيرة الأجل |

### 3️⃣ ملفات الإعدادات والسياسات

| الملف | الموقع | الغرض |
|------|--------|-------|
| `policy.yml` | `contracts/impute/policy.yml` | سياسات الجودة والحدود الجغرافية |
| `kpis.yml` | `contracts/kpis.yml` | تعريفات الـ KPIs |

---

## 📤 المخرجات (Outputs)

### 1️⃣ المخرجات الرئيسية

#### A. ملفات الرؤى (Insights Files)

| الملف | الوصف | المحتوى |
|------|-------|---------|
| **`insights_report.json`** | التقرير الرسمي للرؤى | - القائمة الرسمية للرؤى المعتمدة<br>- الملخص الإحصائي<br>- المصادر |
| **`insights_candidates.json`** | المرشحات الاستكشافية | - جميع المرشحات بما فيها غير المعتمدة<br>- التشخيصات التفصيلية<br>- الأعلام (flags) |
| **`story_ops.json`** | القصص التشغيلية | - بطاقات قابلة للتنفيذ<br>- توصيات عملية<br>- الأولويات |
| **`cards.json`** | ✨ **جديد!** بطاقات الرؤى | - بطاقات منفصلة للواجهة<br>- التوصيات المباشرة |
| **`narratives.json`** | ✨ **جديد!** السرديات ثنائية اللغة | - سرد عربي وإنجليزي<br>- وصف العلاقات<br>- المقاييس الأساسية |

#### B. ملفات التحكم والجودة

| الملف | الوصف |
|------|-------|
| **`gate.json`** | حالة البوابة (PASS/WARN/STOP) |
| **`diagnostics.json`** | التشخيصات التفصيلية والتحذيرات |
| **`column_coverage.json`** | تقرير تغطية الأعمدة |
| **`quality_report.json`** | تقرير الجودة الشامل |

#### C. ملفات الإحصائيات

| الملف | الوصف |
|------|-------|
| **`basic_stats.json`** | إحصائيات أساسية (mean, median, p90) |
| **`segment_stats.parquet`** | إحصائيات حسب القطاعات (segments) |
| **`time_stats.parquet`** | إحصائيات زمنية |
| **`text_stats.json`** | إحصائيات نصية |
| **`keyphrases_topk.json`** | أكثر العبارات شيوعاً |

#### D. ملفات Dashboard

| الملف | الوصف |
|------|-------|
| **`dashboard_data.parquet`** | ✨ **جديد!** بيانات جاهزة لـ ECharts |

#### E. ملفات Layer 2 (اختيارية)

| الملف | الوصف |
|------|-------|
| **`layer2/layer2_snapshot.json`** | لقطة شاملة لـ Layer 2 |
| **`layer2/variance_analysis.json`** | تحليل التباين |
| **`layer2/comparative_summary.json`** | الملخص المقارن |
| **`layer2/heatmap_matrix.json`** | مصفوفة الحرارة |

#### F. ملفات السجلات

| الملف | الوصف |
|------|-------|
| **`logs.jsonl`** | سجل الأحداث التفصيلي |

#### G. تحليلات متقدمة (Advanced Analytics)

| الملف | الوصف |
|------|-------|
| `advanced/cluster_summary.json` | ملخص التجميع (مصدره KNIME أو fallback الداخلي) |
| `advanced/anomalies.json` | كشف الشذوذ (Isolation Forest أو fallback المبني داخل المرحلة) |
| `advanced/correlation_matrix.json` | مصفوفة ارتباط مهيكلة للوحة BI |
| `advanced/orders_forecast.parquet` | تنبؤات قصيرة الأجل (3 فترات مستقبلية) |
| `advanced/summary.json` | ملف تلخيص يوضح مصدر كل مخرج (KNIME مقابل fallback) |

> **ملاحظة:** Stage 08 ينسخ مخرجات KNIME عندما تكون متاحة، ويولد fallback خفيف من `features.parquet` عندما تغيب هذه الملفات لضمان استمرارية لوحة التحليلات.

---

## 🔄 منطق العمل (Workflow Logic)

### المرحلة 1: التحميل والتحضير
```
1. تحميل الإعدادات (Stage08Settings)
2. تحميل السياسات (policy.yml)
3. تحميل البيانات:
   ├─ features.parquet
   ├─ correlations_kpi.json / correlations.json
   ├─ redundancy.json
   └─ ملفات اختيارية (text, sentiment, layer2)
```

### المرحلة 2: الفحوصات الأولية (Preflight Checks)
```
1. فحص البيانات المفقودة (Missing Data):
   ├─ الأعمدة الحرجة (critical columns)
   ├─ الأعمدة الجغرافية (geo columns) - سياسة خاصة
   └─ العتبات (thresholds):
       ├─ WARN: 10% (قياسي) أو 60% (جغرافي)
       └─ STOP: 20% (قياسي) أو 95% (جغرافي)

2. فحص التواريخ المستقبلية:
   └─ إذا وُجدت → STOP

3. فحص تغطية الأعمدة:
   └─ إسقاط الأعمدة ذات البيانات المفقودة > 90%

النتيجة: PASS / WARN / STOP
```

### المرحلة 3: تطبيع الارتباطات
```
1. تحويل التنسيقات القديمة إلى KPI-based format
2. التحقق من وجود kpi و feature في كل entry
3. إنشاء rel_key = "kpi|feature"
```

### المرحلة 4: اكتشاف الشذوذات (Anomaly Detection)
```
1. الطريقة الأساسية (Z-score):
   ├─ Metric: COD_AMOUNT
   ├─ Sigma: 3.0
   ├─ Min N: 300
   └─ Group by: segments

2. الطريقة البديلة (Adapter):
   ├─ Flag: USE_EXT_KPI_ANOMALY_SCORING=1
   ├─ Library: PyOD IsolationForest
   └─ Fallback إلى Z-score عند الفشل
```

### المرحلة 5: معالجة العينات (Sampling)
```
إذا كانت الصفوف > 5M و enable_sampling_over_5m = True:
└─ أخذ عينة: 50% من البيانات (قابل للتعديل)
```

### المرحلة 6: تصنيف الأعمدة (Column Categorization)
```
لكل عمود:
├─ numeric: أعداد عشرية أو في numeric_hints
├─ binary: قيمتان فقط (0/1, True/False)
├─ categorical: نصوص مع عدد محدود من القيم
└─ other: باقي الأنواع
```

### المرحلة 7: حساب المقاييس (Metrics Computation)

#### A. المقاييس الأولية (Primary Metrics)
```
حسب نوع البيانات:

1. binary × binary → Phi Coefficient (φ)
   ├─ Effect: φ = (ad - bc) / √[(a+b)(c+d)(a+c)(b+d)]
   ├─ Risk Difference
   ├─ Odds Ratio
   └─ Lift

2. binary × numeric → Point-Biserial r
   ├─ Effect: correlation(binary, numeric)
   ├─ Cohen's d
   └─ CI 95%

3. categorical × binary → Cramér's V
   ├─ Effect: V = √[χ²/(n × min_dim)]
   └─ Positive rates per category

4. numeric × numeric → Pearson r
   ├─ Effect: Pearson correlation
   └─ Spearman ρ (rank correlation)
```

#### B. مقاييس الاستقرار (Stability Metrics)

```
1. Time Stability (استقرار عبر الزمن):
   ├─ تقسيم البيانات إلى نوافذ زمنية:
   │  ├─ T2: آخر 30 يوم (قابل للتعديل)
   │  └─ T1: 30 يوم قبلها
   ├─ حساب المقياس في كل نافذة
   ├─ مقارنة الاتجاهات (directions)
   └─ Score = 1 - |effect_T1 - effect_T2|

2. Segment Stability (استقرار عبر القطاعات):
   ├─ تقسيم البيانات حسب segments:
   │  ├─ CARRIER
   │  ├─ REGION
   │  └─ وغيرها (max 150 segment)
   ├─ حساب المقياس في كل قطاع
   ├─ مقارنة الاتجاهات
   └─ Score = aligned_segments / total_segments

3. Holdout Stability (استقرار بالتقسيم):
   ├─ تقسيم البيانات: 80% train / 20% holdout
   ├─ حساب المقياس في كل مجموعة
   └─ Score = 1 - |effect_train - effect_holdout|

Stability Score النهائي = متوسط الثلاثة
```

#### C. الثقة والقوة (Confidence & Strength)

```
1. Strength (القوة):
   └─ abs(effect_size) محدودة بـ [0, 1]

2. Coverage (التغطية):
   └─ n / total_rows

3. Confidence (الثقة):
   └─ weighted average:
       ├─ 60% × strength
       ├─ 25% × stability_score
       └─ 15% × coverage

4. Signal Score (درجة الإشارة):
   └─ للترتيب:
       ├─ 45% × strength
       ├─ 30% × stability
       ├─ 15% × coverage
       └─ 10% × (1 - redundancy)
```

### المرحلة 8: تصنيف المرشحات (Candidate Classification)

```
1. Flags (الأعلام):
   ├─ small_n: إذا كان n < 300
   ├─ simpson: كشف تناقض سيمبسون (معطل افتراضياً)
   └─ may_conflict_with: تعارضات محتملة

2. التصنيف:
   ├─ Official (الرسمية):
   │  ├─ confidence >= 0.50
   │  ├─ NOT small_n
   │  ├─ NOT simpson
   │  └─ NOT low_signal
   └─ Exploratory (الاستكشافية):
       └─ جميع المرشحات

3. Confidence Buckets:
   ├─ HIGH: >= 0.70
   ├─ MEDIUM: >= 0.50 و < 0.70
   └─ LOW: < 0.50
```

### المرحلة 9: التحكم بالبوابة (Gate Control)

```
Status Decision:

1. STOP إذا:
   ├─ preflight checks فشلت
   ├─ لا يوجد official insights
   └─ جميع المرشحات محظورة بـ flags

2. WARN إذا:
   ├─ فقط low-signal candidates
   ├─ لا يوجد correlations تتجاوز العتبة
   └─ بعض official insights < 0.70

3. PASS إذا:
   └─ جميع official insights >= 0.70
```

### المرحلة 10: توليد المخرجات

```
1. Insights Report (التقرير الرسمي)
2. Story Cards (البطاقات التشغيلية)
3. Cards.json (✨ جديد!)
4. Narratives.json (✨ جديد! - ثنائي اللغة)
5. Dashboard Data (✨ جديد! - Parquet للـ ECharts)
6. Diagnostics & Quality Reports
7. Statistics (segments, time, text, basic)
8. Layer 2 Integration (إن وُجد)
9. Anomalies Report
10. Logs (JSONL)
```

---

## 🔗 العلاقات مع المراحل الأخرى

### المراحل السابقة (Upstream Dependencies)

```
Stage 06 (Feature Engineering)
    │
    ├─ features.parquet → البيانات الأساسية
    │
    ↓
Stage 07 (Correlations)
    │
    ├─ correlations_kpi.json → الارتباطات
    ├─ redundancy.json → التكرار
    │
    ↓
Stage 07.5 (Feature Report) [اختياري]
    │
    ├─ variance_analysis.json
    ├─ comparative_summary.json
    ├─ heatmap_matrix.json
    │
    ↓
Stage 03.5 (TextOps) [اختياري]
    │
    ├─ text_profile.json
    ├─ sentiment_features.parquet
    │
    ↓
KNIME Profile [اختياري]
    │
    └─ layer2_candidate.json
```

### المراحل اللاحقة (Downstream Consumers)

```
Stage 08 (Insights)
    │
    ├─ insights_report.json
    ├─ story_ops.json
    ├─ cards.json
    ├─ narratives.json
    ├─ dashboard_data.parquet
    ├─ diagnostics.json
    │
    ↓
Stage 09 (Business Validation)
    │
    └─ يستخدم insights لـ:
        ├─ SLA validation
        ├─ What-if scenarios
        └─ Executive summaries
    ↓
Stage 10 (BI Delivery)
    │
    └─ يستخدم:
        ├─ dashboard_data.parquet
        ├─ narratives.json
        └─ insights_report.json
```

---

## ⚙️ الإعدادات الرئيسية (Key Settings)

### 1. عتبات الثقة (Confidence Thresholds)
```python
emit_threshold: 0.50       # الحد الأدنى للنشر
high_bucket: 0.70          # عتبة الثقة العالية
confidence_weights: (0.60, 0.25, 0.15)  # strength, stability, coverage
```

### 2. حدود المعالجة (Processing Limits)
```python
max_features: 200          # أقصى عدد features للمعالجة
max_segments: 150          # أقصى عدد segments
n_min_per_segment: 300     # الحد الأدنى للعينة
max_cells_seg_time: 2000   # حد grid seg×time
```

### 3. النوافذ الزمنية (Time Windows)
```python
time_window_days: 60       # نافذة التحليل الكلية
split_windows: (30, 30)    # T2, T1 بالأيام
business_hours: (8, 20)    # ساعات العمل
```

### 4. العينات (Sampling)
```python
enable_sampling_over_5m: True
sample_fraction: 0.5
sampling_threshold_rows: 5_000_000
```

### 5. تغطية البيانات (Data Coverage)
```python
missing_ratio_threshold: 0.90      # إسقاط الأعمدة
critical_missing_warn: 0.10        # تحذير
critical_missing_stop: 0.20        # إيقاف
```

### 6. المميزات المتقدمة (Advanced Features)
```python
enable_seg_time: False              # معطل افتراضياً (resource-heavy)
enable_simpson_detect: False        # كشف تناقض سيمبسون
enable_contrast_sets: False
enable_partial_stratified: True
enable_permutation: False
enable_bh_fdr: False
```

---

## 🎯 الخوارزميات الأساسية

### 1. Point-Biserial Correlation
```python
def _point_biserial(binary: Series, numeric: Series) -> float:
    """
    حساب الارتباط بين متغير ثنائي ومتغير عددي
    
    Returns: r ∈ [-1, 1]
    - Positive: القيم العددية أعلى عند binary=1
    - Negative: القيم العددية أقل عند binary=1
    """
```

### 2. Phi Coefficient
```python
def _phi_coefficient(a, b, c, d) -> float:
    """
    حساب الارتباط بين متغيرين ثنائيين
    
    Contingency Table:
           KPI=1  KPI=0
    F=1      a      b
    F=0      c      d
    
    φ = (ad - bc) / √[(a+b)(c+d)(a+c)(b+d)]
    Returns: φ ∈ [-1, 1]
    """
```

### 3. Cramér's V
```python
def _cramers_v(contingency: ndarray) -> float:
    """
    حساب الارتباط بين متغير قاطع ومتغير ثنائي
    
    V = √[χ²/(n × min_dim)]
    Returns: V ∈ [0, 1]
    """
```

### 4. Pearson & Spearman
```python
def _pearson_spearman(df, x, y) -> Tuple[float, float]:
    """
    حساب ارتباطات بيرسون (خطي) وسبيرمان (رتبي)
    
    Returns: (pearson_r, spearman_ρ)
    Both ∈ [-1, 1]
    """
```

### 5. Z-Score Anomaly Detection
```python
def _anomalies(df, by, metric, sigma=3.0, min_n=300):
    """
    كشف الشذوذات باستخدام Z-score
    
    For each group in 'by':
    1. Calculate mean(μ) and std(σ)
    2. z = (x - μ) / σ
    3. Flag if |z| > sigma (default 3.0)
    
    Returns: DataFrame مع z_score column
    """
```

---

## 📊 أمثلة على المخرجات

### مثال: insights_report.json
```json
{
  "run_id": "demo-2025-11-04",
  "generated_at": "2025-11-04T10:30:00Z",
  "summary": {
    "official_count": 15,
    "exploratory_count": 45,
    "n_rows": 125000,
    "max_strength": 0.85,
    "max_confidence": 0.92,
    "median_confidence": 0.68
  },
  "insights": [
    {
      "kpi": "cod_amount",
      "relation": "delivery_time <-> cod_amount",
      "direction": "negative",
      "strength": 0.72,
      "confidence": 0.85,
      "coverage": 0.94,
      "stability_score": 0.88,
      "n": 118000,
      "bucket": "HIGH",
      "evidence": [
        "artifacts/{run_id}/stage_07_correlations/correlations_kpi.json",
        "stage07_source:numeric",
        "corr_method:pearson"
      ]
    }
  ]
}
```

### مثال: narratives.json (✨ جديد!)
```json
{
  "run_id": "demo-2025-11-04",
  "generated_at": "2025-11-04T10:30:00Z",
  "count": 15,
  "narratives": [
    {
      "id": "cod_amount_delivery_time",
      "kpi": "cod_amount",
      "feature": "delivery_time",
      "narrative_ar": "العلاقة بين delivery_time وcod_amount تُظهر ارتباطاً سلبية بقوة 0.72 وثقة 0.85. هذه العلاقة تغطي 94.0% من البيانات وتستند إلى 118000 ملاحظة.",
      "narrative_en": "The relationship between delivery_time and cod_amount shows a Negative association with strength 0.72 and confidence 0.85. This relationship covers 94.0% of the data and is based on 118000 observations.",
      "direction": "negative",
      "strength": 0.72,
      "confidence": 0.85,
      "coverage": 0.94,
      "n": 118000
    }
  ]
}
```

### مثال: cards.json (✨ جديد!)
```json
{
  "run_id": "demo-2025-11-04",
  "generated_at": "2025-11-04T10:30:00Z",
  "count": 15,
  "cards": [
    {
      "title": "delivery_time linked with cod_amount (Global)",
      "what_we_see": "We observe lower cod amount when delivery time shifts in Global.",
      "where": "Global",
      "action_now": [
        "Review operational levers tied to delivery_time within Global.",
        "Pilot an intervention on delivery_time and monitor cod_amount."
      ],
      "expected_effect": "Measurable change within 2-4 weeks",
      "priority": "High",
      "kpi": "cod_amount",
      "window": "Recent window",
      "n": 118000
    }
  ]
}
```

### مثال: gate.json
```json
{
  "status": "PASS",
  "counts": {
    "all": 45,
    "emitted": 15
  },
  "reasons": [],
  "diag": {
    "preflight": {
      "status": "PASS",
      "reasons": [],
      "warnings": [],
      "profile": {
        "n_rows": 125000,
        "window_start": "2025-09-01T00:00:00+03:00",
        "window_end": "2025-10-31T23:59:59+03:00",
        "window_days": 60
      }
    }
  },
  "low_signal_candidates": 0,
  "policy": {
    "path": "contracts/impute/policy.yml",
    "geo_warn_threshold": 0.6,
    "geo_stop_threshold": 0.95,
    "geo_columns": ["latitude", "longitude"]
  }
}
```

---

## 🚨 الأخطاء الشائعة (Common Issues)

### 1. STOP بسبب البيانات المفقودة
```
Symptom: gate.json status = "STOP"
Reason: "Critical column 'latitude' missing ratio 0.25 exceeds 20% threshold"

الحل:
1. راجع سياسة policy.yml
2. أضف الأعمدة إلى allow_high_missing_columns
3. أو حسّن جودة البيانات في المراحل السابقة
```

### 2. لا توجد رؤى رسمية
```
Symptom: insights_report.json → "insights": []
Reason: جميع المرشحات confidence < 0.50

الحل:
1. راجع correlations من Stage 07
2. تحقق من min_corr_strength في Stage 07
3. قد تحتاج feature engineering أفضل في Stage 06
```

### 3. تحذير low-signal candidates
```
Symptom: gate.json status = "WARN"
Reason: "Only low-signal fallback candidates were available"

الحل:
1. هذا يعني الارتباطات ضعيفة
2. راجع جودة البيانات
3. قد تحتاج features إضافية أو تحسين KPIs
```

### 4. فشل Layer 2
```
Symptom: لا توجد layer2/ في المخرجات
Reason: ملفات Layer 2 غير موجودة من Stage 07.5

الحل:
1. هذا اختياري - ليس خطأ
2. إذا كنت تريده، تأكد من تشغيل Stage 07.5
3. أو تشغيل KNIME workflow
```

---

## 🔧 التعديلات والتخصيص

### 1. تغيير عتبة الثقة
```yaml
# config/stage_08.yml
emit_threshold: 0.40  # من 0.50 إلى 0.40 (أكثر تساهلاً)
high_bucket: 0.65     # من 0.70 إلى 0.65
```

### 2. تفعيل Segment×Time Grid
```yaml
enable_seg_time: true  # تحذير: resource-intensive!
max_cells_seg_time: 2000
```

### 3. تغيير سياسة الجودة
```yaml
# contracts/impute/policy.yml
geo:
  columns:
    - latitude
    - longitude
  missing_warn_threshold: 0.7  # من 0.6
  missing_stop_threshold: 0.98  # من 0.95
  allow_high_missing_columns:
    - latitude
    - longitude
```

### 4. إضافة KPIs جديدة
```yaml
# contracts/kpis.yml
- name: customer_satisfaction
  direction: maximize
  threshold: 0.80

- name: delivery_cost
  direction: minimize
  threshold: 50.0
```

---

## 📈 مقاييس الأداء (Performance Metrics)

| الإعداد | الوقت المتوقع | الذاكرة |
|---------|---------------|---------|
| 100K rows, 50 features | ~30 ثانية | ~500 MB |
| 1M rows, 100 features | ~3 دقائق | ~2 GB |
| 5M rows, 200 features (مع sampling) | ~8 دقائق | ~3 GB |
| 10M rows, 200 features (مع sampling) | ~15 دقيقة | ~4 GB |

---

## 🎓 ملخص تنفيذي

### ماذا تفعل المرحلة 8؟
تحوّل الارتباطات الإحصائية إلى رؤى تشغيلية مع تقييم موثوقيتها عبر:
- ✅ حساب مقاييس متعددة (Phi, Point-Biserial, Cramér's V, Pearson)
- ✅ تقييم الاستقرار (عبر الزمن، القطاعات، والتقسيم)
- ✅ حساب الثقة (Confidence) بناءً على القوة والاستقرار والتغطية
- ✅ التصنيف إلى رسمية واستكشافية
- ✅ التحكم بالبوابة (PASS/WARN/STOP)
- ✅ توليد قصص وتوصيات تشغيلية
- ✅ إنتاج مخرجات جاهزة للـ BI والـ Dashboard

### أين تُستخدم المخرجات؟
- 📊 **Stage 09**: التحقق من الأعمال وWhat-if scenarios
- 📈 **Stage 10**: BI Delivery وSemantic Layer
- 🎨 **Frontend**: Dashboards (ECharts) وNarratives
- 👥 **Stakeholders**: التقارير التنفيذية والقرارات

### المميزات الجديدة (Recent Additions):
- ✨ **cards.json**: بطاقات منفصلة للواجهة
- ✨ **narratives.json**: سرديات ثنائية اللغة (عربي/إنجليزي)
- ✨ **dashboard_data.parquet**: بيانات جاهزة لـ ECharts
- ✨ **تحسينات Anomaly Detection**: PyOD adapter اختياري

---

**آخر تحديث**: 4 نوفمبر 2025  
**الإصدار**: Mind-Q V4.1  
**الفرع**: `port/update-2025-10-11`
