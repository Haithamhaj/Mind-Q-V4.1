# خطة الإصلاح #1: مصدر بيانات المرحلة 8

**الحالة:** جاهز للمراجعة والموافقة  
**الأولوية:** 🔴 عالية جداً (Critical)  
**التأثير:** حل مشكلة عدم وجود رؤى في النظام

---

## 📋 المشكلة الحالية

### التشخيص
- **الأعراض**: جميع الرؤى في المرحلة 8 تحمل علامة `low_signal: true`
- **الارتباطات**: ضعيفة جداً (max r=0.017)
- **السبب الجذري**: المرحلة 8 تقرأ البيانات من ملف `features.parquet` الصادر عن المرحلة 6 (Standardize)
- **المشكلة**: التطبيع (normalization) في المرحلة 6 يدمر التباين (variance) في بعض الأعمدة

### المسار الحالي
```
المرحلة 5 (Impute) 
    ↓ clean_imputed.parquet
المرحلة 6 (Standardize + Normalize)
    ↓ features.parquet [← المشكلة: بيانات معيارية بتباين منخفض]
المرحلة 8 (Insights)
    ↓ correlations ≈ 0
```

### البيانات المتاحة من المرحلة 7

#### 1. المرحلة 07 (Readiness)
**المخرجات:**
- ✅ `correlations_kpi.json` - ارتباطات KPI
- ✅ `correlations.json` - ارتباطات عامة
- ✅ `business_correlations.json` - ارتباطات الأعمال
- ✅ `redundancy.json` - تفاصيل التكرار
- ✅ `decision_manifest.json` - قرارات الجاهزية
- ✅ `layer1_catalog.json` - كتالوج Layer 1
- ✅ `kpi_candidates.json` - مرشحي KPI

#### 2. المرحلة 07.5 (Feature Report)
**المخرجات:**
- ✅ `variance_analysis.json` - تحليل التباين
- ✅ `comparative_summary.json` - ملخص مقارن
- ✅ `heatmap_matrix.json` - مصفوفة heatmap
- ✅ `report.json` - تقرير كامل

#### 3. المرحلة 07.6 (LLM Summary)
**المخرجات:**
- ✅ `executive_summary.md` - ملخص تنفيذي
- ✅ `recommendations.json` - توصيات LLM بالعربية
  - `column_name` - اسم العمود
  - `reason` - سبب التوصية (بالعربية)
  - `evidence_key` - مفتاح الدليل
- ✅ `summary.json` - ملخص + توصيات
- ✅ `metrics.json` - معلومات LLM (tokens, cost, model)

#### 4. المرحلة 07.7 (Business Correlations)
**المخرجات:**
- ✅ `business_correlations.json` - ارتباطات الأعمال المتقدمة
- ✅ `business_correlations.parquet` - نسخة جدولية
- ✅ `summary.json` - ملخص الارتباطات
- ✅ `network.json` - رسم بياني شبكي

---

## 🎯 الحل المقترح

### النهج الجديد: دمج كامل لمخرجات المرحلة 7

```
المرحلة 5 (Impute)
    ↓ clean_imputed.parquet
المرحلة 6 (Features)
    ↓ features.parquet (قبل التطبيع)
المرحلة 7 (+ فروعها)
    ├─ 07 Readiness      → correlations_kpi.json
    ├─ 07.5 Reports      → variance_analysis.json, heatmap_matrix.json
    ├─ 07.6 LLM Summary  → recommendations.json (Arabic)
    └─ 07.7 Correlations → business_correlations.json
         ↓ [جميع المخرجات تُدمج]
المرحلة 8 (Insights)
    ↓ رؤى غنية + توصيات LLM + ارتباطات متقدمة
```

---

## 🔧 التعديلات المطلوبة

### 1. تعديل `backend/src/app/services/stage_08_insights/impl.py`

#### 1.1 دالة `_load_inputs()` (السطر 525-552)

**التعديل الحالي:**
```python
paths = {
    "features": base / "stage_06_feature_eng" / "features.parquet",
    "correlations": correlations_kpi if correlations_kpi.exists() else correlations_legacy,
    "correlations_source": correlations_legacy,
    "redundancy": corr_dir / "redundancy.json",
    "text_profile": base / "stage_03_5_textops" / "text_profile.json",
    "sentiment": base / "stage_03_5_textops" / "sentiment_features.parquet",
    "layer2_variance": feature_report_dir / "variance_analysis.json",
    "layer2_compare": feature_report_dir / "comparative_summary.json",
    "layer2_heatmap": feature_report_dir / "heatmap_matrix.json",
    "layer2_candidate": knime_profile_dir / "layer2_candidate.json",
}
```

**التعديل المقترح:**
```python
# إضافة مسارات جديدة للمرحلة 7 بفروعها
llm_summary_dir = base / "stage_07_6_llm_summary"
business_corr_dir = base / "stage_07_7_business_correlations"

paths = {
    # البيانات الأساسية (من المرحلة 5 أو 6 قبل التطبيع)
    "features": base / "stage_05_impute" / "clean_imputed.parquet",
    
    # ارتباطات من المرحلة 7
    "correlations": correlations_kpi if correlations_kpi.exists() else correlations_legacy,
    "correlations_source": correlations_legacy,
    "redundancy": corr_dir / "redundancy.json",
    
    # ارتباطات الأعمال المتقدمة (07.7)
    "business_correlations": business_corr_dir / "business_correlations.json",
    "business_summary": business_corr_dir / "summary.json",
    "network_graph": business_corr_dir / "network.json",
    
    # توصيات LLM (07.6)
    "llm_recommendations": llm_summary_dir / "recommendations.json",
    "llm_summary": llm_summary_dir / "summary.json",
    "executive_summary": llm_summary_dir / "executive_summary.md",
    
    # تقارير الميزات (07.5)
    "layer2_variance": feature_report_dir / "variance_analysis.json",
    "layer2_compare": feature_report_dir / "comparative_summary.json",
    "layer2_heatmap": feature_report_dir / "heatmap_matrix.json",
    
    # كتالوج الجاهزية (07)
    "layer1_catalog": readiness_dir / "layer1_catalog.json",
    "decision_manifest": readiness_dir / "decision_manifest.json",
    "kpi_candidates": readiness_dir / "kpi_candidates.json",
    
    # TextOps (03.5)
    "text_profile": base / "stage_03_5_textops" / "text_profile.json",
    "sentiment": base / "stage_03_5_textops" / "sentiment_features.parquet",
}
```

#### 1.2 دالة جديدة: `_load_llm_recommendations()`

```python
def _load_llm_recommendations(recommendations_path: Path) -> List[Dict[str, Any]]:
    """
    تحميل توصيات LLM من المرحلة 07.6
    
    العودة:
        List of {
            "column_name": str,
            "reason": str (بالعربية),
            "evidence_key": str,
            "confidence": float (مستنتج من evidence)
        }
    """
    if not recommendations_path.exists():
        return []
    
    try:
        payload = json.loads(recommendations_path.read_text(encoding="utf-8"))
        recommendations = payload.get("recommendations", [])
        
        enriched = []
        for rec in recommendations:
            enriched.append({
                "column_name": rec.get("column_name", ""),
                "reason_ar": rec.get("reason", ""),
                "evidence_key": rec.get("evidence_key", ""),
                "source": "llm_stage_07_6",
                "confidence": 0.85,  # افتراضياً للتوصيات من LLM
            })
        
        return enriched
    except Exception as e:
        logger.warning(f"Failed to load LLM recommendations: {e}")
        return []
```

#### 1.3 دالة جديدة: `_load_business_correlations()`

```python
def _load_business_correlations(business_corr_path: Path) -> Dict[str, Any]:
    """
    تحميل ارتباطات الأعمال المتقدمة من المرحلة 07.7
    
    العودة:
        {
            "numeric_numeric": [...],
            "numeric_categorical": [...],
            "categorical_categorical": [...]
        }
    """
    if not business_corr_path.exists():
        return {"numeric_numeric": [], "numeric_categorical": [], "categorical_categorical": []}
    
    try:
        payload = json.loads(business_corr_path.read_text(encoding="utf-8"))
        return {
            "numeric_numeric": payload.get("numeric_numeric", []),
            "numeric_categorical": payload.get("numeric_categorical", []),
            "categorical_categorical": payload.get("categorical_categorical", []),
            "summary": payload.get("summary", {}),
        }
    except Exception as e:
        logger.warning(f"Failed to load business correlations: {e}")
        return {"numeric_numeric": [], "numeric_categorical": [], "categorical_categorical": []}
```

#### 1.4 تعديل دالة `run()` الرئيسية

**إضافة بعد تحميل المدخلات:**

```python
# تحميل توصيات LLM
llm_recommendations = []
if paths["llm_recommendations"].exists():
    llm_recommendations = _load_llm_recommendations(paths["llm_recommendations"])
    logger.info(f"Loaded {len(llm_recommendations)} LLM recommendations from Stage 07.6")

# تحميل ارتباطات الأعمال
business_correlations = {}
if paths["business_correlations"].exists():
    business_correlations = _load_business_correlations(paths["business_correlations"])
    logger.info(f"Loaded business correlations from Stage 07.7")

# تحميل كتالوج Layer 1
layer1_catalog = {}
if paths["layer1_catalog"].exists():
    try:
        layer1_catalog = json.loads(paths["layer1_catalog"].read_text(encoding="utf-8"))
    except Exception:
        pass
```

### 2. دمج توصيات LLM في الرؤى

**إضافة قسم جديد في `cards.json`:**

```python
# في نهاية دالة run()، قبل كتابة cards.json
llm_insights_section = {
    "source": "llm_stage_07_6",
    "title": {
        "ar": "توصيات ذكاء اصطناعي",
        "en": "AI Recommendations"
    },
    "recommendations": llm_recommendations,
    "count": len(llm_recommendations),
}

# إضافة إلى cards payload
final_cards_payload = {
    **cards_payload,
    "llm_insights": llm_insights_section,
}
```

### 3. دمج ارتباطات الأعمال في التحليلات

**تعزيز قوة الارتباطات باستخدام Business Correlations:**

```python
def _enrich_correlations_with_business_data(
    candidates: List[CandidateRecord],
    business_correlations: Dict[str, Any]
) -> List[CandidateRecord]:
    """
    تعزيز المرشحين ببيانات الارتباطات من المرحلة 07.7
    """
    business_map = {}
    
    # بناء خريطة من ارتباطات الأعمال
    for corr in business_correlations.get("numeric_numeric", []):
        key = f"{corr['feature_a']}_{corr['feature_b']}"
        business_map[key] = corr
    
    # تعزيز المرشحين
    enriched = []
    for candidate in candidates:
        key = f"{candidate.feature}_{candidate.kpi}"
        if key in business_map:
            business_corr = business_map[key]
            # تحديث قوة الارتباط
            candidate.strength = max(
                candidate.strength,
                abs(business_corr.get("correlation", 0.0))
            )
            candidate.notes.append(f"Enhanced with business correlation: {business_corr.get('kind', '')}")
        enriched.append(candidate)
    
    return enriched
```

---

## 📊 النتائج المتوقعة

### قبل الإصلاح
```json
{
  "official_insights": [],
  "exploratory_insights": [
    {
      "kpi": "cod_amount",
      "strength": 0.017,
      "low_signal": true,
      "confidence": 0.45
    }
  ]
}
```

### بعد الإصلاح
```json
{
  "official_insights": [
    {
      "kpi": "cod_amount",
      "feature": "delivery_region",
      "strength": 0.42,
      "confidence": 0.87,
      "source": "stage_07_7_business_correlations",
      "low_signal": false
    }
  ],
  "llm_insights": {
    "recommendations": [
      {
        "column_name": "delivery_region",
        "reason_ar": "المنطقة تؤثر بشكل كبير على قيمة COD بنسبة 42%",
        "confidence": 0.85
      }
    ]
  },
  "exploratory_insights": [...]
}
```

---

## ✅ خطوات التنفيذ (بالترتيب)

### المرحلة 1: التحضير
- [ ] مراجعة وفهم هيكل مخرجات المرحلة 7 بفروعها الأربعة
- [ ] التأكد من أن جميع المراحل 07, 07.5, 07.6, 07.7 تعمل بشكل صحيح
- [ ] اختبار مخرجات كل مرحلة على البيانات الحالية

### المرحلة 2: تعديل الكود
- [ ] تعديل دالة `_load_inputs()` لإضافة المسارات الجديدة
- [ ] إنشاء دالة `_load_llm_recommendations()`
- [ ] إنشاء دالة `_load_business_correlations()`
- [ ] إنشاء دالة `_enrich_correlations_with_business_data()`
- [ ] تعديل دالة `run()` الرئيسية لدمج البيانات الجديدة

### المرحلة 3: التكامل
- [ ] دمج توصيات LLM في `cards.json`
- [ ] دمج ارتباطات الأعمال في حساب الرؤى
- [ ] تحديث منطق `_partition_candidates()` للاستفادة من البيانات الجديدة
- [ ] إضافة metadata للرؤى لتوضيح المصدر (07, 07.5, 07.6, 07.7)

### المرحلة 4: الاختبار
- [ ] اختبار تحميل البيانات من جميع المصادر
- [ ] اختبار دمج توصيات LLM
- [ ] اختبار دمج ارتباطات الأعمال
- [ ] التحقق من أن الرؤى الآن أقوى (strength > 0.15)
- [ ] التحقق من أن `low_signal: false` لمعظم الرؤى

### المرحلة 5: التحقق
- [ ] تشغيل المسار الكامل من 01 إلى 10
- [ ] مراجعة `cards.json` للتأكد من وجود رؤى
- [ ] مراجعة `narratives.json` للتأكد من السرديات
- [ ] التحقق من أن BI يظهر البيانات

---

## ⚠️ التحذيرات والملاحظات

1. **تغيير مصدر البيانات**:
   - تغيير من `stage_06_feature_eng/features.parquet` إلى `stage_05_impute/clean_imputed.parquet`
   - يجب التأكد من أن المرحلة 5 تُنتج بيانات نظيفة بدون normalization

2. **التوافق مع الكود الحالي**:
   - المرحلة 8 تتوقع أعمدة معينة، يجب التأكد من توافق البيانات
   - قد تحتاج بعض الدوال للتعديل لدعم البيانات غير المعيارية

3. **الأداء**:
   - إضافة مصادر بيانات جديدة قد يزيد وقت التنفيذ
   - يجب استخدام lazy loading للملفات الكبيرة

4. **LLM Recommendations**:
   - التوصيات بالعربية، يجب دعم UTF-8 في جميع الملفات
   - قد تكون بعض التوصيات عامة، يجب فلترتها

---

## 🎯 مؤشرات النجاح

- ✅ **الارتباطات**: قوة الارتباطات > 0.15 (بدلاً من 0.017)
- ✅ **الرؤى الرسمية**: عدد الرؤى official > 0 (بدلاً من 0)
- ✅ **علامة low_signal**: نسبة الرؤى بـ `low_signal: false` > 60%
- ✅ **توصيات LLM**: توصيات بالعربية موجودة في `cards.json`
- ✅ **ارتباطات الأعمال**: تعزيز الرؤى ببيانات المرحلة 07.7
- ✅ **BI غير فارغ**: وجود بيانات في dashboard

---

## 📝 ملاحظات للتنفيذ

1. **أولوية التنفيذ**: هذه الخطة لها الأولوية القصوى قبل الخطط الأخرى
2. **الاختبار التدريجي**: تنفيذ كل مرحلة واختبارها قبل الانتقال للتالية
3. **التوثيق**: توثيق كل تغيير في replit.md
4. **Rollback Plan**: الاحتفاظ بنسخة من الكود القديم للعودة إليه إذا لزم الأمر

---

**الحالة النهائية**: ⏸️ **جاهز للمراجعة - بانتظار الموافقة**
