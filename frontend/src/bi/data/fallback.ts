import type {
  BiDatasetRow,
  CorrelationCollection,
  DimensionsCatalog,
  Insight,
  KnimeDataSnapshot,
  KnimeReport,
  MetricSpec,
} from "./types";
export { fallbackIntelligence } from "./intelligence";

export const fallbackMetrics: MetricSpec[] = [
  {
    id: "orders_volume",
    title: "Orders Volume",
    formula: "MAX(kpi_orders_cnt)",
    unit: "count",
    fmt: "integer",
    join_keys: ["entity_id", "scenario_id"],
    time_col: "ts",
  },
  {
    id: "cod_collected_total",
    title: "COD Collected (Total)",
    formula: "MAX(kpi_cod_total)",
    unit: "amount",
    currency: "SAR",
    fmt: "sar_currency",
    join_keys: ["entity_id", "scenario_id"],
    time_col: "ts",
  },
  {
    id: "cod_average_ticket",
    title: "COD Average Ticket",
    formula: "AVG(kpi_cod_avg)",
    unit: "amount",
    currency: "SAR",
    fmt: "sar_currency",
    time_col: "ts",
  },
  {
    id: "cod_conversion_rate",
    title: "COD Conversion Rate",
    formula: "AVG(kpi_cod_rate)",
    unit: "ratio",
    fmt: "percentage",
    time_col: "ts",
  },
  {
    id: "effect_size_confidence",
    title: "Effect Size Confidence",
    formula: "AVG(eff_confidence)",
    unit: "ratio",
    fmt: "percentage",
    time_col: "ts",
  },
];

export const fallbackDimensions: DimensionsCatalog = {
  generated_at: undefined,
  row_count: undefined,
  date: [{ name: "ts" }],
  numeric: [
    { name: "kpi_orders_cnt" },
    { name: "kpi_cod_total" },
    { name: "kpi_cod_avg" },
    { name: "kpi_cod_rate" },
    { name: "eff_confidence" },
  ],
  categorical: [
    { name: "entity_id" },
    { name: "scenario_id" },
    { name: "DESTINATION" },
    { name: "STATUS" },
    { name: "RECEIVER_MODE" },
  ],
  bool: [],
};

export const fallbackInsights: Insight[] = [];

export const fallbackDataset: BiDatasetRow[] = [];

export const fallbackCorrelations: CorrelationCollection = {
  numeric: [],
  datetime: [],
  business: {
    numeric_numeric: [],
    numeric_categorical: [],
    categorical_categorical: [],
  },
  sources: {},
  run: "fallback",
  artifacts_root: null,
  top: null,
};

export const fallbackKnimeData: KnimeDataSnapshot = {
  run: "fallback",
  columns: [],
  rows: [],
  total_rows: 0,
  limit: 0,
  offset: 0,
  path: undefined,
  updated_at: undefined,
  size_bytes: undefined,
};

export const fallbackKnimeReport: KnimeReport = {
  dq_report: { results: [], source: null },
  dq_coverage: null,
  insights: { items: [], meta: null, source: null },
  layer2_candidate: null,
  bridge_summary: null,
  exports: [],
  notes: null,
  profile_files: [],
  extras: null,
};
