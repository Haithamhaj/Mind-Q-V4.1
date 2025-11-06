import type { PipelineRunInfo, SchemaTerminologyRecord } from "@/lib/api";
import type { Layer3Intelligence } from "./intelligence";

export type MetricSpec = {
  id: string;
  title?: string;
  formula?: string;
  unit?: string;
  currency?: string;
  fmt?: string;
  join_keys?: string[];
  time_col?: string | null;
};

export type DimensionSpec = {
  name: string;
  dtype?: string;
  non_null?: number;
  cardinality?: number;
};

export type DimensionsCatalog = {
  generated_at?: string;
  row_count?: number;
  date: DimensionSpec[];
  numeric: DimensionSpec[];
  categorical: DimensionSpec[];
  bool: DimensionSpec[];
};

export type InsightDriver = {
  dimension: string;
  value: string;
  impact?: number | null;
};

export type Insight = {
  id: string;
  type: string;
  kpi?: string;
  title: string;
  summary?: string;
  severity?: string;
  delta?: number | null;
  delta_type?: string;
  timestamp?: string | null;
  drivers?: InsightDriver[];
  source?: string;
  recommendations?: string[];
  next_steps?: string[];
  metrics_context?: Record<string, unknown>;
  tags?: string[];
  deltas?: Record<string, number>;
  delta_descriptions?: Record<
    string,
    {
      value?: number | null;
      formatted?: string | null;
      movement?: string | null;
    }
  >;
};

export type BiDatasetRow = Record<string, unknown>;

export type CorrelationPair = {
  feature_a: string;
  feature_b: string;
  correlation?: number | null;
  abs_correlation?: number | null;
  sample_size?: number | null;
  kind?: string;
  method?: string;
  source?: string | null;
  p_value?: number | null;
  feature_a_label?: string;
  feature_b_label?: string;
  feature_a_domain?: string;
  feature_b_domain?: string;
  feature_a_sensitivity?: string;
  feature_b_sensitivity?: string;
  feature_a_description?: string;
  feature_b_description?: string;
  business_label?: string;
  impact_summary?: string;
  sensitivity?: string;
  kpi_tag?: string | null;
  kpi_label?: string | null;
  kpi_direction?: string | null;
  kpi_unit?: string | null;
  kpi_feature?: string | null;
  impact_driver_feature?: string | null;
  impact_driver_label?: string | null;
  effect_direction?: string | null;
  effect_is_positive?: boolean | null;
  expected_kpi_delta?: number | null;
  expected_kpi_delta_pct?: number | null;
  driver_domain?: string | null;
  is_persistent?: boolean;
  history_runs?: string[];
};

export type BusinessCorrelation = {
  feature_a: string;
  feature_b: string;
  correlation?: number | null;
  abs_correlation?: number | null;
  sample_size?: number | null;
  method?: string;
  kind?: string;
  notes?: Record<string, unknown>;
  p_value?: number | null;
  feature_a_label?: string;
  feature_b_label?: string;
  feature_a_domain?: string;
  feature_b_domain?: string;
  feature_a_sensitivity?: string;
  feature_b_sensitivity?: string;
  feature_a_description?: string;
  feature_b_description?: string;
  business_label?: string;
  impact_summary?: string;
  sensitivity?: string;
  kpi_tag?: string | null;
  kpi_label?: string | null;
  kpi_direction?: string | null;
  kpi_unit?: string | null;
  kpi_feature?: string | null;
  impact_driver_feature?: string | null;
  impact_driver_label?: string | null;
  effect_direction?: string | null;
  effect_is_positive?: boolean | null;
  expected_kpi_delta?: number | null;
  expected_kpi_delta_pct?: number | null;
  driver_domain?: string | null;
  is_persistent?: boolean;
  history_runs?: string[];
};

export type BusinessCorrelationGroups = {
  numeric_numeric: BusinessCorrelation[];
  numeric_categorical: BusinessCorrelation[];
  categorical_categorical: BusinessCorrelation[];
};

export type CorrelationCollection = {
  numeric: CorrelationPair[];
  datetime: CorrelationPair[];
  business: BusinessCorrelationGroups | null;
  sources?: {
    numeric?: string | null;
    datetime?: string | null;
    business?: string | null;
  };
  run?: string | null;
  artifacts_root?: string | null;
  top?: number | null;
};

export type InsightStats = {
  insights_total?: number;
  by_type?: Record<string, number>;
};

export type KpiCatalogColumnPolicy = {
  name: string;
  classification?: string;
  include_in_bi_feed?: boolean;
  include_in_semantic?: boolean;
  include_in_exports?: boolean;
  tags?: string[];
  description?: string;
};

export type KpiCatalogEntry = {
  name: string;
  expr?: string;
  dtype?: string;
  description?: string;
  owner?: string;
  business_goal?: string;
  ml_usage?: string;
  default_dimensions?: string[];
  tags?: string[];
  visibility?: string;
  freshness_sla_hours?: number;
  quality_notes?: string;
  llm_prompt?: string;
};

export type KpiCatalog = {
  version?: number;
  thresholds?: Record<string, number>;
  kpis?: KpiCatalogEntry[];
  columns?: KpiCatalogColumnPolicy[];
};

export type KnimeDataRow = Record<string, unknown>;

export type KnimeDataPreview = KnimeDataRow[];

export type KnimeDataSnapshot = {
  run: string;
  columns: string[];
  rows: KnimeDataPreview;
  total_rows: number;
  limit: number;
  offset: number;
  path?: string;
  updated_at?: string;
  size_bytes?: number;
};

export type KnimeDQResult = {
  id?: string;
  status?: string;
  passed?: boolean;
  title?: string;
  severity?: string;
  scope?: string;
  entity?: string;
  fail_rate?: number;
  evaluated_rows?: number;
  failed_rows?: number;
  notes?: string;
  sample_failures_path?: string;
};

export type KnimeDQReport = {
  results: KnimeDQResult[];
  source?: string | null;
};

export type KnimeDQCoverage = {
  summary?: Record<string, number | string>;
  source?: string | null;
};

export type KnimeInsightRecord = {
  headline?: string;
  [key: string]: unknown;
};

export type KnimeInsightsPayload = {
  items: KnimeInsightRecord[];
  meta?: Record<string, unknown> | null;
  source?: string | null;
};

export type KnimeExport = {
  path: string;
  relative_path?: string;
  format?: string;
  domain?: string | null;
  table?: string | null;
  version?: string | null;
  size_bytes?: number | null;
  updated_at?: string | null;
  rows?: number | null;
  columns?: string[] | null;
};

export type KnimeProfileFile = {
  name: string;
  path: string;
  size_bytes?: number | null;
  updated_at?: string | null;
};

export type KnimeClusterSummary = {
  cluster: number;
  records: number;
  share: number;
  avg_lead_time_hours?: number;
  avg_cod_amount?: number;
  avg_weight_kg?: number;
  avg_amount?: number;
};

export type KnimeAnomalyRow = Record<string, unknown>;

export type KnimeCorrelationPair = {
  feature_a: string;
  feature_b: string;
  correlation: number;
  abs_correlation: number;
};

export type KnimeForecastPoint = {
  timestamp: string;
  value: number;
};

export type KnimeReportExtras = {
  clusters?: {
    features: string[];
    summary: KnimeClusterSummary[];
  };
  anomalies?: {
    columns: string[];
    identifier_columns?: string[];
    rows: KnimeAnomalyRow[];
  };
  correlations?: {
    pairs: KnimeCorrelationPair[];
  };
  forecast?: {
    metric: string;
    history: KnimeForecastPoint[];
    predictions: KnimeForecastPoint[];
    window_used?: number;
  };
};

export type KnimeReport = {
  dq_report: KnimeDQReport;
  dq_coverage?: KnimeDQCoverage | null;
  insights: KnimeInsightsPayload;
  layer2_candidate?: {
    source?: string | null;
    payload?: Record<string, unknown> | null;
  } | null;
  bridge_summary?: {
    source?: string | null;
    payload?: Record<string, unknown> | null;
  } | null;
  exports: KnimeExport[];
  notes?: {
    run_summary?: string | null;
    source?: string | null;
  } | null;
  profile_files: KnimeProfileFile[];
  extras?: KnimeReportExtras | null;
};

export type CatalogMetadata = {
  metrics?: Record<string, unknown>;
  dimensions?: Record<string, unknown>;
  insights?: Record<string, unknown>;
  kpiCatalog?: KpiCatalog;
};

export type Layer2AgentMessage = {
  role: "user" | "assistant";
  content: string;
};

export type Layer2AgentRequest = {
  question: string;
  history?: Layer2AgentMessage[];
  filters?: Record<string, string[]>;
  run?: string;
};

export type Layer2AgentRecommendation = {
  metricId?: string | null;
  metricLabel?: string | null;
  dimension?: string | null;
  chart?: string | null;
  filters: Record<string, string[]>;
  rationale?: string | null;
  language?: string | null;
  confidence?: string | null;
};

export type Layer2AgentResultContext = {
  metrics?: Array<{ id?: string | null; title?: string | null; unit?: string | null; fmt?: string | null }>;
  dimensions?: Record<string, string[]>;
  samples?: Record<string, string[]>;
  filters?: Record<string, string[]>;
};

export type Layer2AgentResult = {
  reply: string;
  recommendation: Layer2AgentRecommendation;
  provider: string;
  model: string;
  tokensIn: number;
  tokensOut: number;
  costEstimate?: number;
  durationSeconds?: number;
  usedFallback: boolean;
  context?: Layer2AgentResultContext;
};

export type BiDataContextValue = {
  runId: string;
  setRunId: (runId: string) => void;
  availableRuns: PipelineRunInfo[];
  runsLoading: boolean;
  runsError?: string;
  refreshRuns: () => Promise<void>;
  metrics: MetricSpec[];
  dimensions: DimensionsCatalog;
  insights: Insight[];
  dataset: BiDatasetRow[];
  correlations: CorrelationCollection;
  intelligence: Layer3Intelligence;
  knimeData: KnimeDataSnapshot | null;
  knimeReport: KnimeReport | null;
  loading: boolean;
  error?: string;
  filters: Record<string, string[]>;
  setFilter: (dimension: string, values: string[]) => void;
  insightStats?: InsightStats;
  catalogMeta: CatalogMetadata;
  runLayer2Assistant: (request: Layer2AgentRequest) => Promise<Layer2AgentResult>;
  schemaGlossary: {
    records: SchemaTerminologyRecord[];
    aliases: Record<string, string[]>;
    loading: boolean;
    error?: string;
  };
  refreshSchemaGlossary: () => Promise<void>;
};

