# KNIME Advanced Analytics Fallback

Last updated: 2025-10-29  
Owner: Mind-Q Technical Team

## Overview

The BI Intelligence view now surfaces richer KNIME outputs:

- Segment clustering (KMeans)
- Shipment anomaly detection (Isolation Forest)
- High-impact numeric correlations
- Short-horizon demand forecasts

When KNIME publishes specialised artefacts they are honoured. If a file is missing, the backend derives a lightweight fallback from `phase_07_knime/data.parquet` so analysts still receive actionable summaries.

## Fallback Details

| Analytic | Source columns (required) | Default output |
|----------|--------------------------|----------------|
| Clusters | `lead_time_hours`, `COD_AMOUNT`, `weight_kg`, `amount` (أي عمودين فأكثر) | حتى 4 شرائح مع الحصة ومتوسط زمن التسليم |
| Anomalies | نفس الأعمدة العددية أعلاه | أهم 20 عملية شاذة مع score ومعرّفات الطلب |
| Correlations | كل الأعمدة العددية المتاحة | حتى 15 زوجاً بقيمة |ρ| ≥ 0.25 |
| Forecast | `order_date` → `entry_date` → `ts` | توقع 3 أيام لمتوسط الطلب اليومي |

> **ملاحظة:** في حال لم تتوفر مكتبة `scikit-learn` سيتم تخطي خوارزميات التجزئة والكشف عن الشذوذ مع تسجيل تحذير.

## الاعتمادات المطلوبة

- `numpy`
- `pandas`
- `pyarrow` (مستخدمة بالفعل في المشروع)
- `scikit-learn` (اختيارية – لازمة للتجزئة والكشف عن الشذوذ)

تثبيت سريع:

```bash
pip install numpy pandas scikit-learn
```

## ترقية مخرجات KNIME نفسها

لإلغاء الحاجة إلى fallback وإدخال مخرجات مخصّصة من KNIME:

1. افتح `knime/phase07_feature_app.knwf`.
2. أضف عقداً للتجزئة والشذوذ والارتباط والتوقعات، ثم احفظ المخرجات في:
   - `profile/cluster_summary.json`
   - `profile/anomalies.json`
   - `profile/correlation_matrix.json`
   - `transforms/forecast/orders_forecast__v1.parquet`
3. شغّل `pwsh knime/run_knime_workflow.ps1 -RunId <RUN_ID>`.
4. سيقوم الـ API بإظهار تلك الملفات مباشرة داخل لوحة ذكاء الأعمال.

## تجربة الواجهة

اللوحة تعرض الآن:

- بطاقات ملخصة (عدد قواعد الجودة، الإنذارات، الرؤى، الجداول، تغطية DQ)
- قائمة أهم إنذارات الجودة مع روابط للملفات
- رؤى إحصائية مع توضيح FDR
- قائمة الجداول المصدّرة
- **جديد:** شرائح KMeans، جدول الشحنات الشاذة، أهم الارتباطات، توقعات الطلب القصيرة

## استكشاف الأخطاء

- غياب الأقسام غالباً يعني نقص الأعمدة في ملف Stage 06؛ راجع `data.parquet`.
- ثبّت `scikit-learn` محلياً إذا كانت أقسام التجزئة أو الشذوذ فارغة. |
