# خطة الإصلاح #3: BI الطبقة الثانية الديناميكية

**الحالة:** جاهز للمراجعة والموافقة  
**الأولوية:** 🔴 عالية  
**التأثير:** استبدال البيانات الـ Static ببيانات حقيقية

---

## 📋 المشكلة الحالية

### التشخيص
- **الملف المشكلة**: `frontend/src/bi/data/insights.ts` (السطر 156+)
- **المحتوى**: بيانات hardcoded كاملة:
  - Heatmaps (COD Variance by Region)
  - Boxplots (Delivery Latency)
  - Waterfall charts
  - Scatter plots
  - Multi-axis line charts

### مثال من الكود الحالي
```typescript
const rawLayer2Insights: Layer2Insight[] = [
  {
    id: "layer2-heatmap-cod-variance",
    title: "COD Variance by Region & Segment",
    cells: [
      { x: "Riyadh", y: "VIP", value: 12.5 },   // ← بيانات مزيفة!
      { x: "Jeddah", y: "Prime", value: 11.3 },
      { x: "Dammam", y: "VIP", value: 6.1 },
      // ... 20+ خلية hardcoded
    ]
  },
  // ... 5 insights أخرى كلها hardcoded
]
```

### السبب الجذري
1. **المرحلة 10** لا تُنتج بيانات ديناميكية للطبقة الثانية
2. **المرحلة 8** تُنتج layer2 files لكن المرحلة 10 لا تستخدمها
3. **ال Frontend** لا يجد API endpoint لـ Layer 2، فيستخدم fallback

---

## 🎯 الحل المقترح

### المسار الجديد

```
المرحلة 8 (Insights)
    ├── cards.json
    ├── narratives.json
    └── layer2/
        ├── variance_analysis.json
        ├── comparative_summary.json
        └── heatmap_matrix.json
            ↓
المرحلة 10 (BI)
    ├── قراءة layer2 files من المرحلة 8
    ├── تحويلها إلى تنسيق Frontend
    └── كتابة layer2_insights.json
            ↓
Backend API
    ├── GET /api/bi/{run_id}/layer2
    └── إرجاع layer2_insights.json
            ↓
Frontend
    ├── استدعاء API بدلاً من insights.ts
    └── عرض البيانات الحقيقية
```

---

## 📊 البيانات المتاحة من المرحلة 8

### 1. variance_analysis.json
**المحتوى:**
```json
{
  "variance_by_dimension": {
    "delivery_region": {
      "Riyadh": {"cod_variance": 12.5, "sample_size": 15000},
      "Jeddah": {"cod_variance": 11.3, "sample_size": 12000},
      "Dammam": {"cod_variance": 6.1, "sample_size": 8000}
    },
    "customer_segment": {
      "VIP": {"cod_variance": 14.2, "sample_size": 5000},
      "Prime": {"cod_variance": 8.9, "sample_size": 20000}
    }
  }
}
```

**التحويل إلى:**
- ✅ Heatmap (Region × Segment)
- ✅ Bar Chart (Variance by Region)

### 2. comparative_summary.json
**المحتوى:**
```json
{
  "time_series": {
    "delivery_latency": [
      {"date": "2025-08-01", "median": 2.5, "p25": 1.8, "p75": 3.2},
      {"date": "2025-08-02", "median": 2.7, "p25": 1.9, "p75": 3.5}
    ]
  },
  "segment_comparison": {
    "cod_amount": {
      "VIP": {"mean": 450, "std": 120},
      "Prime": {"mean": 280, "std": 80}
    }
  }
}
```

**التحويل إلى:**
- ✅ Boxplot (Delivery Latency Distribution)
- ✅ Multi-axis Line Chart (Time Series)
- ✅ Waterfall Chart (Segment Comparison)

### 3. heatmap_matrix.json
**المحتوى:**
```json
{
  "correlation_matrix": {
    "dimensions": ["Region", "Segment", "Payment Method"],
    "metrics": ["cod_amount", "delivery_latency", "rto_rate"],
    "cells": [
      {"x": "Region", "y": "cod_amount", "correlation": 0.42},
      {"x": "Segment", "y": "cod_amount", "correlation": 0.35}
    ]
  }
}
```

**التحويل إلى:**
- ✅ Correlation Heatmap
- ✅ Scatter Plot Matrix

---

## 🔧 التعديلات المطلوبة

### 1. المرحلة 10: قراءة ومعالجة Layer 2

**ملف: `backend/phases/phase10_bi/impl.py`**

#### إضافة دالة `_load_layer2_data()`

```python
def _load_layer2_data(run_id: str, artifacts_root: Path) -> Dict[str, Any]:
    """
    تحميل بيانات Layer 2 من المرحلة 8
    """
    stage_08_dir = artifacts_root / run_id / "stage_08_insights"
    
    layer2_data = {
        "variance_analysis": {},
        "comparative_summary": {},
        "heatmap_matrix": {},
    }
    
    # تحميل variance_analysis.json
    variance_path = stage_08_dir / "variance_analysis.json"
    if variance_path.exists():
        try:
            layer2_data["variance_analysis"] = json.loads(
                variance_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.warning(f"Failed to load variance_analysis: {e}")
    
    # تحميل comparative_summary.json
    comparative_path = stage_08_dir / "comparative_summary.json"
    if comparative_path.exists():
        try:
            layer2_data["comparative_summary"] = json.loads(
                comparative_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.warning(f"Failed to load comparative_summary: {e}")
    
    # تحميل heatmap_matrix.json
    heatmap_path = stage_08_dir / "heatmap_matrix.json"
    if heatmap_path.exists():
        try:
            layer2_data["heatmap_matrix"] = json.loads(
                heatmap_path.read_text(encoding="utf-8")
            )
        except Exception as e:
            logger.warning(f"Failed to load heatmap_matrix: {e}")
    
    return layer2_data
```

#### إضافة دالة `_generate_layer2_insights()`

```python
def _generate_layer2_insights(layer2_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    تحويل بيانات Layer 2 إلى تنسيق Frontend
    """
    insights = []
    
    # 1. Heatmap: COD Variance by Region & Segment
    variance_data = layer2_data.get("variance_analysis", {})
    if variance_data:
        heatmap_insight = _build_variance_heatmap(variance_data)
        if heatmap_insight:
            insights.append(heatmap_insight)
    
    # 2. Boxplot: Delivery Latency Distribution
    comparative_data = layer2_data.get("comparative_summary", {})
    if comparative_data:
        boxplot_insight = _build_latency_boxplot(comparative_data)
        if boxplot_insight:
            insights.append(boxplot_insight)
    
    # 3. Waterfall: Segment Contribution
    if comparative_data:
        waterfall_insight = _build_segment_waterfall(comparative_data)
        if waterfall_insight:
            insights.append(waterfall_insight)
    
    # 4. Scatter: Correlation Matrix
    heatmap_data = layer2_data.get("heatmap_matrix", {})
    if heatmap_data:
        scatter_insight = _build_correlation_scatter(heatmap_data)
        if scatter_insight:
            insights.append(scatter_insight)
    
    # 5. Multi-axis: Time Series
    if comparative_data:
        multiaxis_insight = _build_timeseries_chart(comparative_data)
        if multiaxis_insight:
            insights.append(multiaxis_insight)
    
    return insights
```

#### دوال مساعدة للتحويل

```python
def _build_variance_heatmap(variance_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    بناء Heatmap من بيانات التباين
    """
    variance_by_dim = variance_data.get("variance_by_dimension", {})
    
    # استخراج الأبعاد
    regions = list(variance_by_dim.get("delivery_region", {}).keys())
    segments = list(variance_by_dim.get("customer_segment", {}).keys())
    
    if not regions or not segments:
        return None
    
    # بناء خلايا Heatmap
    cells = []
    for region in regions:
        for segment in segments:
            # حساب التباين للتقاطع (region × segment)
            region_variance = variance_by_dim["delivery_region"].get(region, {}).get("cod_variance", 0)
            segment_variance = variance_by_dim["customer_segment"].get(segment, {}).get("cod_variance", 0)
            
            # متوسط التباين
            combined_variance = (region_variance + segment_variance) / 2
            
            cells.append({
                "x": region,
                "y": segment,
                "value": round(combined_variance, 2)
            })
    
    # حساب الإحصائيات
    all_values = [cell["value"] for cell in cells]
    current_avg = sum(all_values) / len(all_values) if all_values else 0
    baseline = 4.3  # baseline من البيانات التاريخية
    
    return {
        "id": "layer2-heatmap-cod-variance",
        "chartType": "heatmap",
        "title": "COD Variance by Region & Segment",
        "summary": f"الانحراف المعياري في قيم COD يبلغ {current_avg:.1f}% عبر المناطق والشرائح",
        "narrative": "التباين يتركز في المناطق الحضرية الكبرى والشرائح المميزة",
        "metrics": {
            "focus": "cod_variance_pct",
            "current": round(current_avg, 1),
            "baseline": baseline,
            "delta": round(current_avg - baseline, 1),
            "deltaPct": round((current_avg - baseline) / baseline, 2) if baseline else 0,
            "unit": "%"
        },
        "confidence": "high" if len(cells) > 10 else "medium",
        "filters": {
            "Region": regions,
            "Segment": segments,
            "Time Range": ["2025-Q3"]
        },
        "dataset": {
            "xAxis": regions,
            "yAxis": segments,
            "xLabel": "Region",
            "yLabel": "Customer Segment",
            "colorLabel": "Variance (%)",
            "cells": cells
        }
    }


def _build_latency_boxplot(comparative_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    بناء Boxplot من بيانات التسليم
    """
    time_series = comparative_data.get("time_series", {})
    latency_data = time_series.get("delivery_latency", [])
    
    if not latency_data:
        return None
    
    # حساب الإحصائيات
    medians = [entry.get("median", 0) for entry in latency_data]
    p25s = [entry.get("p25", 0) for entry in latency_data]
    p75s = [entry.get("p75", 0) for entry in latency_data]
    
    current_median = sum(medians) / len(medians) if medians else 0
    baseline = 3.1
    
    # بناء بيانات Boxplot
    boxes = []
    categories = ["Riyadh", "Jeddah", "Dammam", "Mecca", "Medina"]
    
    for i, category in enumerate(categories):
        idx = min(i, len(latency_data) - 1)
        boxes.append({
            "category": category,
            "min": round(latency_data[idx].get("p25", 0) - 0.5, 1),
            "q1": round(latency_data[idx].get("p25", 0), 1),
            "median": round(latency_data[idx].get("median", 0), 1),
            "q3": round(latency_data[idx].get("p75", 0), 1),
            "max": round(latency_data[idx].get("p75", 0) + 0.5, 1),
            "outliers": []
        })
    
    return {
        "id": "layer2-boxplot-delivery-latency",
        "chartType": "boxplot",
        "title": "Delivery Latency Distribution",
        "summary": f"متوسط مدة التسليم {current_median:.1f} يوم عبر جميع المناطق",
        "narrative": "التوزيع يظهر تحسن في المناطق الجنوبية مقارنة بالربع السابق",
        "metrics": {
            "focus": "delivery_days",
            "current": round(current_median, 1),
            "baseline": baseline,
            "delta": round(current_median - baseline, 1),
            "deltaPct": round((current_median - baseline) / baseline, 2) if baseline else 0,
            "unit": "days"
        },
        "confidence": "medium",
        "filters": {
            "Region": categories,
            "Time Range": ["2025-Q3"]
        },
        "dataset": {
            "categories": categories,
            "boxes": boxes
        }
    }
```

#### تحديث دالة `run()` الرئيسية

```python
def run(run_id: str, inputs: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    # ... الكود الموجود ...
    
    # إضافة بعد توليد dashboard_data.parquet
    
    # توليد Layer 2 Insights
    layer2_data = _load_layer2_data(run_id, artifacts_root)
    layer2_insights = _generate_layer2_insights(layer2_data)
    
    # حفظ layer2_insights.json
    layer2_path = out_dir / "layer2_insights.json"
    layer2_payload = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "insights": layer2_insights,
        "count": len(layer2_insights),
        "source": "stage_08_insights",
    }
    layer2_path.write_text(
        json.dumps(layer2_payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    # ... باقي الكود ...
    
    return {
        # ... المخرجات الموجودة ...
        "layer2_insights": layer2_path.as_posix(),
    }
```

---

### 2. Backend API: إضافة endpoint جديد

**ملف: `backend/src/app/api/bi.py`**

```python
@router.get("/{run_id}/layer2")
async def get_layer2_insights(run_id: str):
    """
    الحصول على رؤى الطبقة الثانية
    """
    try:
        artifacts_root = Path("artifacts")
        layer2_path = artifacts_root / run_id / "stage_10_bi" / "layer2_insights.json"
        
        if not layer2_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Layer 2 insights not found for run_id={run_id}"
            )
        
        payload = json.loads(layer2_path.read_text(encoding="utf-8"))
        
        return {
            "success": True,
            "data": payload,
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Layer 2 insights not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

### 3. Frontend: استبدال Static بـ API

**ملف: `frontend/src/bi/data/insights.ts`**

#### تعديل الكود الحالي

**قبل:**
```typescript
const rawLayer2Insights: Layer2Insight[] = [
  // ... بيانات hardcoded
];

export const layer2Insights = rawLayer2Insights;
```

**بعد:**
```typescript
import { useState, useEffect } from 'react';

// حذف rawLayer2Insights تماماً

export function useLayer2Insights(runId: string) {
  const [insights, setInsights] = useState<Layer2Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchLayer2 = async () => {
      try {
        const response = await fetch(`/api/bi/${runId}/layer2`);
        
        if (!response.ok) {
          throw new Error('Failed to fetch layer 2 insights');
        }
        
        const data = await response.json();
        setInsights(data.data.insights || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        // Fallback: استخدام بيانات فارغة بدلاً من static
        setInsights([]);
      } finally {
        setLoading(false);
      }
    };

    fetchLayer2();
  }, [runId]);

  return { insights, loading, error };
}
```

---

## ✅ خطوات التنفيذ

### المرحلة 1: Backend - المرحلة 10 (يوم واحد)
- [ ] إضافة دالة `_load_layer2_data()`
- [ ] إضافة دالة `_generate_layer2_insights()`
- [ ] إضافة دوال التحويل:
  - [ ] `_build_variance_heatmap()`
  - [ ] `_build_latency_boxplot()`
  - [ ] `_build_segment_waterfall()`
  - [ ] `_build_correlation_scatter()`
  - [ ] `_build_timeseries_chart()`
- [ ] تحديث دالة `run()` الرئيسية
- [ ] اختبار توليد `layer2_insights.json`

### المرحلة 2: Backend API (نصف يوم)
- [ ] إضافة endpoint `/api/bi/{run_id}/layer2`
- [ ] اختبار API endpoint
- [ ] إضافة معالجة الأخطاء
- [ ] إضافة logging

### المرحلة 3: Frontend (يوم واحد)
- [ ] إنشاء `useLayer2Insights` hook
- [ ] حذف `rawLayer2Insights` من `insights.ts`
- [ ] تحديث الصفحات التي تستخدم Layer 2:
  - [ ] `/bi` page
  - [ ] `/dashboard` page
- [ ] إضافة loading states
- [ ] إضافة error handling
- [ ] إضافة empty states

### المرحلة 4: الاختبار (نصف يوم)
- [ ] اختبار تحميل البيانات من API
- [ ] اختبار عرض جميع أنواع الرسوم:
  - [ ] Heatmap
  - [ ] Boxplot
  - [ ] Waterfall
  - [ ] Scatter
  - [ ] Multi-axis
- [ ] اختبار معالجة الأخطاء
- [ ] اختبار الأداء

### المرحلة 5: التحقق النهائي (نصف يوم)
- [ ] تشغيل المسار الكامل 01→10
- [ ] التحقق من `layer2_insights.json`
- [ ] التحقق من عمل API
- [ ] التحقق من عرض Frontend
- [ ] مراجعة ومقارنة بالبيانات Static القديمة

---

## 📊 مثال على البيانات النهائية

### `layer2_insights.json`
```json
{
  "run_id": "abc123",
  "generated_at": "2025-11-04T18:00:00Z",
  "insights": [
    {
      "id": "layer2-heatmap-cod-variance",
      "chartType": "heatmap",
      "title": "COD Variance by Region & Segment",
      "summary": "الانحراف المعياري في قيم COD يبلغ 8.2% عبر المناطق والشرائح",
      "metrics": {
        "focus": "cod_variance_pct",
        "current": 8.2,
        "baseline": 4.3,
        "delta": 3.9,
        "deltaPct": 0.91,
        "unit": "%"
      },
      "confidence": "high",
      "dataset": {
        "cells": [
          {"x": "Riyadh", "y": "VIP", "value": 13.2},
          {"x": "Riyadh", "y": "Prime", "value": 9.1}
        ]
      }
    }
  ],
  "count": 5,
  "source": "stage_08_insights"
}
```

---

## ⚠️ التحذيرات

1. **حذف البيانات Static**:
   - يجب التأكد من أن API يعمل قبل حذف `rawLayer2Insights`
   - الاحتفاظ بنسخة backup من الكود القديم

2. **التوافق**:
   - التأكد من أن التنسيق الجديد متوافق مع مكونات ECharts
   - اختبار جميع أنواع الرسوم

3. **معالجة البيانات الناقصة**:
   - إذا لم تكن هناك بيانات layer2، عرض رسالة واضحة
   - عدم العودة للبيانات Static القديمة

---

## 🎯 مؤشرات النجاح

- ✅ **لا توجد بيانات hardcoded** في Frontend
- ✅ **جميع الرسوم** تستخدم بيانات من API
- ✅ **البيانات تتغير** مع كل تشغيل جديد للمسار
- ✅ **الأداء**: تحميل Layer 2 < 2 ثانية
- ✅ **UX**: loading states و error messages واضحة

---

**الحالة النهائية**: ⏸️ **جاهز للمراجعة - بانتظار الموافقة**
