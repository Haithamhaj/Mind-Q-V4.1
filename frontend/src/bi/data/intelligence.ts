"use client";

import { z } from "zod";

const intelligenceNetworkNode = z.object({
  id: z.string(),
  label: z.string(),
  type: z.enum(["kpi", "feature", "segment", "bucket"]).default("feature"),
  score: z.number().optional(),
  category: z.number().optional(),
});

const intelligenceNetworkEdge = z.object({
  source: z.string(),
  target: z.string(),
  value: z.number(),
  label: z.string().optional(),
});

const intelligenceNetworkSchema = z.object({
  nodes: z.array(intelligenceNetworkNode),
  edges: z.array(intelligenceNetworkEdge),
  categories: z.array(z.string()).optional(),
});

const intelligenceSankeySchema = z.object({
  nodes: z.array(z.string()),
  links: z.array(
    z.object({
      source: z.string(),
      target: z.string(),
      value: z.number(),
      label: z.string().optional(),
    }),
  ),
  unit: z.string().optional(),
});

const intelligenceAnomalySeriesSchema = z.object({
  name: z.string(),
  points: z.array(
    z.object({
      timestamp: z.string(),
      value: z.number(),
      share: z.number().optional(),
    }),
  ),
});

const intelligenceAnomalySchema = z.object({
  timestamp: z.string(),
  label: z.string(),
  severity: z.enum(["medium", "high", "critical"]).optional(),
  score: z.number().optional(),
});

const intelligenceTimelineSchema = z.object({
  metric: z.string(),
  series: z.array(intelligenceAnomalySeriesSchema),
  anomalies: z.array(intelligenceAnomalySchema),
});

const predictiveSeriesSchema = z.object({
  name: z.string(),
  kind: z.enum(["actual", "forecast", "baseline"]).default("actual"),
  points: z.array(
    z.object({
      timestamp: z.string(),
      value: z.number(),
    }),
  ),
});

const intelligencePredictiveSchema = z.object({
  metric: z.string(),
  unit: z.string().optional(),
  horizon: z.string().optional(),
  series: z.array(predictiveSeriesSchema),
});

const knimeFileSchema = z.object({
  name: z.string(),
  path: z.string(),
  updated_at: z.string().optional(),
  size_bytes: z.number().optional(),
  summary: z.string().optional(),
});

const knimeParquetSchema = z.object({
  path: z.string().optional(),
  rows: z.number().optional(),
  columns: z.array(z.string()).optional(),
  preview: z.array(z.record(z.string(), z.unknown())).optional(),
  updated_at: z.string().optional(),
  size_bytes: z.number().optional(),
  error: z.string().optional(),
});

const knimeReportSummarySchema = z
  .object({
    dq_rules: z.number().optional(),
    dq_failed: z.number().optional(),
    insight_count: z.number().optional(),
    export_count: z.number().optional(),
    coverage: z.number().optional(),
  })
  .optional();

const knimeSummarySchema = z.object({
  run_id: z.string().optional(),
  mode: z.string().optional(),
  files: z.array(knimeFileSchema),
  metadata: z.record(z.unknown()).optional(),
  data_parquet: knimeParquetSchema.optional(),
  report_summary: knimeReportSummarySchema,
});

const advancedOrdersForecastSchema = z.object({
  path: z.string().optional(),
  rows: z.number().optional(),
  preview: z.array(z.record(z.string(), z.unknown())).optional(),
  error: z.string().optional(),
});

const advancedBundleSchema = z
  .object({
    summary: z.record(z.unknown()).optional(),
    cluster_summary: z.record(z.unknown()).optional(),
    anomalies: z.record(z.unknown()).optional(),
    correlation_matrix: z.record(z.unknown()).optional(),
    orders_forecast: advancedOrdersForecastSchema.optional(),
  })
  .optional();

const nzvImpactSchema = z
  .object({
    low_variance_ignored_columns: z.array(z.record(z.string(), z.unknown())).optional(),
    high_imbalance_included_columns: z.array(z.record(z.string(), z.unknown())).optional(),
    nzv_summary: z.record(z.unknown()).optional(),
  })
  .optional();

const businessGateSchema = z
  .object({
    status: z.string(),
    reasons: z.array(z.string()).optional(),
    counts: z.record(z.unknown()).optional(),
    warnings: z.array(z.string()).optional(),
    nzv_impact: nzvImpactSchema.optional(),
  })
  .optional();

const businessValidationSchema = z
  .object({
    gate: businessGateSchema,
    diagnostics: z.record(z.unknown()).optional(),
    validation_report: z.record(z.unknown()).optional(),
    data_health: z.record(z.unknown()).optional(),
  })
  .optional();

export const layer3IntelligenceSchema = z.object({
  run: z.string(),
  generated_at: z.string(),
  network: intelligenceNetworkSchema,
  sankey: intelligenceSankeySchema,
  anomalies: intelligenceTimelineSchema,
  predictive: intelligencePredictiveSchema,
  knime: knimeSummarySchema,
  advanced: advancedBundleSchema,
  business_validation: businessValidationSchema,
});

export type Layer3Intelligence = z.infer<typeof layer3IntelligenceSchema>;

const sampleLayer3Intelligence: Layer3Intelligence = layer3IntelligenceSchema.parse({
  run: "run-latest",
  generated_at: new Date().toISOString(),
  network: {
    categories: ["kpi", "feature"],
    nodes: [
      { id: "COD_AMOUNT", label: "COD Amount", type: "kpi", score: 0.74, category: 0 },
      { id: "REGION:Riyadh", label: "Riyadh", type: "feature", score: 0.63, category: 1 },
      { id: "SEGMENT:VIP", label: "VIP", type: "feature", score: 0.58, category: 1 },
    ],
    edges: [
      { source: "COD_AMOUNT", target: "REGION:Riyadh", value: 0.68, label: "positive" },
      { source: "COD_AMOUNT", target: "SEGMENT:VIP", value: 0.55, label: "positive" },
    ],
  },
  sankey: {
    nodes: ["COD_AMOUNT", "HIGH", "MEDIUM"],
    links: [
      { source: "COD_AMOUNT", target: "HIGH", value: 0.55, label: "High impact" },
      { source: "COD_AMOUNT", target: "MEDIUM", value: 0.32, label: "Emerging" },
    ],
    unit: "coverage share",
  },
  anomalies: {
    metric: "Orders Volume",
    series: [
      {
        name: "Orders",
        points: [
          { timestamp: "2025-10-20", value: 100, share: 0.2 },
          { timestamp: "2025-10-21", value: 132, share: 0.24 },
          { timestamp: "2025-10-22", value: 168, share: 0.32 },
          { timestamp: "2025-10-23", value: 150, share: 0.3 },
        ],
      },
    ],
    anomalies: [
      { timestamp: "2025-10-22", label: "COD spike - Riyadh VIP", severity: "high", score: 3.2 },
      { timestamp: "2025-10-23", label: "COD plateau - Jeddah Prime", severity: "medium", score: 2.1 },
    ],
  },
  predictive: {
    metric: "Orders Volume",
    unit: "orders",
    horizon: "3d",
    series: [
      {
        name: "Actual",
        kind: "actual",
        points: [
          { timestamp: "2025-10-20", value: 100 },
          { timestamp: "2025-10-21", value: 132 },
          { timestamp: "2025-10-22", value: 168 },
          { timestamp: "2025-10-23", value: 150 },
        ],
      },
      {
        name: "Forecast",
        kind: "forecast",
        points: [
          { timestamp: "2025-10-24", value: 164 },
          { timestamp: "2025-10-25", value: 178 },
          { timestamp: "2025-10-26", value: 192 },
        ],
      },
    ],
  },
  knime: {
    run_id: "run-latest",
    mode: "auto",
    files: [
      {
        name: "layer2_candidate.json",
        path: "artifacts/run-latest/phase_07_knime/profile/layer2_candidate.json",
        updated_at: new Date().toISOString(),
        summary: "Top variance driver: COD_AMOUNT",
      },
      {
        name: "bridge_summary.json",
        path: "artifacts/run-latest/phase_07_knime/profile/bridge_summary.json",
        updated_at: new Date().toISOString(),
        summary: "Bridge approval via auto mode",
      },
    ],
    metadata: {
      prompt: { mode: "auto" },
    },
    data_parquet: {
      path: "artifacts/run-latest/phase_07_knime/data.parquet",
      rows: 1200,
      columns: ["order_id", "destination", "status"],
      preview: [
        { order_id: "ORD-001", destination: "Riyadh", status: "DELIVERED" },
        { order_id: "ORD-002", destination: "Jeddah", status: "IN_TRANSIT" },
        { order_id: "ORD-003", destination: "Riyadh", status: "DELIVERED" },
      ],
      updated_at: new Date().toISOString(),
      size_bytes: 28_704,
    },
    report_summary: {
      dq_rules: 12,
      dq_failed: 2,
      insight_count: 4,
      export_count: 3,
      coverage: 0.92,
    },
  },
  advanced: {
    summary: {
      sources: {
        cluster_summary: { path: "artifacts/run-latest/stage_08_insights/advanced/cluster_summary.json", source: "python" },
        anomalies: { path: "artifacts/run-latest/stage_08_insights/advanced/anomalies.json", source: "python" },
        orders_forecast: { path: "artifacts/run-latest/stage_08_insights/advanced/orders_forecast.parquet", source: "python" },
      },
    },
    cluster_summary: {
      clusters: [
        { id: "Cluster A", count: 180, share: 0.42 },
        { id: "Cluster B", count: 110, share: 0.24 },
      ],
    },
    orders_forecast: {
      path: "artifacts/run-latest/stage_08_insights/advanced/orders_forecast.parquet",
      rows: 3,
      preview: [
        { forecast_date: "2025-10-24T00:00:00+03:00", forecast: 164, step: 1, metric: "COD_AMOUNT" },
        { forecast_date: "2025-10-25T00:00:00+03:00", forecast: 178, step: 2, metric: "COD_AMOUNT" },
        { forecast_date: "2025-10-26T00:00:00+03:00", forecast: 192, step: 3, metric: "COD_AMOUNT" },
      ],
    },
  },
  business_validation: {
    gate: {
      status: "WARN",
      reasons: ["kpi_guard::lead_time_insufficient_n", "stage08::warn"],
      warnings: ["Low-signal fallback candidates present; treat as exploratory signals."],
      nzv_impact: {
        low_variance_ignored_columns: [{ name: "RECEIVER_MODE", nzv_category: "near_zero_variance" }],
        high_imbalance_included_columns: [{ name: "STATUS", dominant_value: "DELIVERED" }],
      },
    },
    diagnostics: {
      decision_counts: { approve: 1800, reject: 120 },
      ops_metric_warnings: ["kpi_guard::sla_pct_insufficient_n"],
      nzv_impact: {
        low_variance_ignored_columns: [{ name: "RECEIVER_MODE", nzv_category: "near_zero_variance" }],
      },
    },
  },
});

export const fallbackIntelligence = sampleLayer3Intelligence;
