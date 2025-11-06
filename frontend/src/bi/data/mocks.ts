import { BiDatasetRow, DimensionsCatalog, Insight, MetricSpec } from "./types";

export const mockMetrics: MetricSpec[] = [
  {
    id: "orders_volume",
    title: "عدد الطلبات",
    formula: "SUM(value)",
    unit: "count",
    time_col: "ts",
  },
  {
    id: "cod_conversion",
    title: "معدل الدفع عند الاستلام",
    formula: "AVG(rate)",
    unit: "ratio",
    time_col: "ts",
  },
];

export const mockDimensions: DimensionsCatalog = {
  generated_at: "2025-10-16T00:00:00Z",
  row_count: 6,
  date: [{ name: "ts", dtype: "datetime64[ns]" }],
  numeric: [
    { name: "value", dtype: "float64" },
    { name: "rate", dtype: "float64" },
  ],
  categorical: [
    { name: "entity_id", dtype: "string", cardinality: 3 },
    { name: "destination", dtype: "string", cardinality: 2 },
  ],
  bool: [],
};

export const mockInsights: Insight[] = [
  {
    id: "anomaly-1",
    type: "anomaly",
    kpi: "orders_volume",
    title: "ارتفاع مفاجئ في الطلبات إلى جدة",
    summary: "الطلبات إلى جدة نمت بنسبة 22% مقارنة بالأسبوع السابق مع مساهمة عالية من COD.",
    severity: "high",
    delta: 0.22,
    delta_type: "delta",
    timestamp: "2025-10-22T00:00:00Z",
    drivers: [
      { dimension: "destination", value: "JED", impact: 0.62 },
      { dimension: "entity_id", value: "ORD-1032", impact: 0.21 },
    ],
    source: "stage_08/anomalies",
    recommendations: [
      "نسّق مع مركز جدة لاستيعاب الطلبات الإضافية دون التأثير على جودة الخدمة.",
      "راجع خطة تحصيل الدفع عند الاستلام لضمان توافر السيولة."
    ],
    next_steps: ["تأكيد النتائج مع فريق المرحلة 09 وتحديث خطة العمليات اليومية."],
    metrics_context: { movement: "ارتفاع", delta_text: "+22.0%" },
    tags: ["شذوذ", "COD"],
  },
  {
    id: "trend-1",
    type: "trend",
    kpi: "cod_conversion",
    title: "تحسن في معدل الدفع عند الاستلام",
    summary: "التغير الأسبوعي: +5.0%؛ التغير السنوي: +9.0%",
    severity: "medium",
    drivers: [
      { dimension: "destination", value: "RUH", impact: 0.55 },
      { dimension: "destination", value: "JED", impact: 0.45 },
    ],
    source: "fallback/phase10",
    recommendations: [
      "تابع استمرار التحسن في الرياض وجدة خلال الأسبوع القادم.",
      "حدّث توقعات التحصيل النقدي بناءً على الاتجاه الحالي."
    ],
    next_steps: ["أدرج المؤشر في تقرير المتابعة اليومية وشارك النتائج مع فريق المبيعات."],
    metrics_context: { movement: "ارتفاع", delta_text: "+5.0%" },
    deltas: { wow: 0.05, yoy: 0.09 },
    tags: ["اتجاه", "COD"],
  },
];

export const mockDataset: BiDatasetRow[] = [
  { entity_id: "ORD-1001", destination: "RUH", ts: "2025-10-08", value: 95, rate: 0.62 },
  { entity_id: "ORD-1002", destination: "RUH", ts: "2025-10-15", value: 110, rate: 0.65 },
  { entity_id: "ORD-1022", destination: "JED", ts: "2025-10-08", value: 80, rate: 0.58 },
  { entity_id: "ORD-1022", destination: "JED", ts: "2025-10-15", value: 130, rate: 0.61 },
  { entity_id: "ORD-1032", destination: "JED", ts: "2025-10-22", value: 154, rate: 0.67 },
  { entity_id: "ORD-1090", destination: "RUH", ts: "2025-10-22", value: 96, rate: 0.64 },
];
