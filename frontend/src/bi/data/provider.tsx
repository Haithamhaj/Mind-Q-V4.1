"use client";

import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";

import { api, type PipelineRunInfo, type SchemaTerminologyRecord } from "@/lib/api";

import {
  fallbackCorrelations,
  fallbackDataset,
  fallbackDimensions,
  fallbackInsights,
  fallbackIntelligence,
  fallbackKnimeData,
  fallbackKnimeReport,
  fallbackMetrics,
} from "./fallback";
import {
  BiDataContextValue,
  BiDatasetRow,
  CatalogMetadata,
  CorrelationCollection,
  DimensionsCatalog,
  Insight,
  InsightStats,
  Layer2AgentRecommendation,
  Layer2AgentRequest,
  Layer2AgentResult,
  Layer2AgentResultContext,
  MetricSpec,
  KpiCatalog,
  KnimeDataSnapshot,
  KnimeReport,
} from "./types";
import { layer3IntelligenceSchema } from "./intelligence";
import type { Layer3Intelligence } from "./intelligence";
import { canonicalizeDimensionValue } from "../utils/normalize";

type EndpointOverrides = Partial<
  Record<
    | "metrics"
    | "dimensions"
    | "insights"
    | "dataset"
    | "correlations"
    | "intelligence"
    | "catalog"
    | "knime"
    | "knimeReport",
    string
  >
>;

type BiDataProviderProps = {
  children: React.ReactNode;
  endpoints?: EndpointOverrides;
};

const MAX_ROWS = 25_000;
const DEFAULT_BASE = process.env.NEXT_PUBLIC_BI_BASE ?? "/api/bi";
// During testing, avoid hardcoded runs; prefer URL ?run=… or latest
const DEFAULT_RUN = "";
const RUN_STORAGE_KEY = "story-bi/run-id";

const BiDataContext = createContext<BiDataContextValue | undefined>(undefined);

type Layer2AgentResponseRaw = {
  reply?: string;
  recommendation?:
    | {
        metric_id?: string | null;
        metric_label?: string | null;
        dimension?: string | null;
        chart?: string | null;
        filters?: Record<string, unknown>;
        rationale?: string | null;
        language?: string | null;
        confidence?: string | null;
      }
    | null;
  provider?: string;
  model?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_estimate?: number;
  duration_s?: number;
  context?: Layer2AgentResultContext;
  used_fallback?: boolean;
};

const EMPTY_DIMENSIONS: DimensionsCatalog = { date: [], numeric: [], categorical: [], bool: [] };
const EMPTY_CORRELATIONS: CorrelationCollection = {
  numeric: [],
  datetime: [],
  business: {
    numeric_numeric: [],
    numeric_categorical: [],
    categorical_categorical: [],
  },
  sources: undefined,
  run: undefined,
  artifacts_root: undefined,
  top: undefined,
};

const clampRows = (rows: BiDatasetRow[] | undefined | null): BiDatasetRow[] => {
  if (!rows?.length) {
    return [];
  }
  return rows.slice(0, MAX_ROWS);
};

const normalizeCategoricalValues = (rows: BiDatasetRow[], dimensions: DimensionsCatalog | undefined | null) => {
  if (!rows.length) {
    return rows;
  }

  const categoricalColumns = new Map(
    (dimensions?.categorical ?? [])
      .map((dimension) => dimension.name?.trim())
      .filter((name): name is string => Boolean(name && name.length > 0))
      .map((name) => [name.toLowerCase(), name]),
  );

  if (!categoricalColumns.size) {
    return rows;
  }

  return rows.map((row) => {
    const normalized: BiDatasetRow = { ...row };
    for (const key of Object.keys(row)) {
      const keyLower = key.trim().toLowerCase();
      if (!categoricalColumns.has(keyLower)) {
        continue;
      }
      const value = row[key];
      if (typeof value !== "string") {
        continue;
      }
      const trimmed = value.trim();
      if (!trimmed) {
        normalized[key] = "";
        continue;
      }
      const collapsed = trimmed.replace(/\s+/g, " ");
      const canonical = canonicalizeDimensionValue(keyLower, collapsed);
      normalized[key] = canonical;
    }
    return normalized;
  });
};

const normaliseAgentFilters = (filters: Record<string, unknown> | undefined): Record<string, string[]> => {
  if (!filters || typeof filters !== "object") {
    return {};
  }
  const normalised: Record<string, string[]> = {};
  for (const [dimension, raw] of Object.entries(filters)) {
    if (!dimension) {
      continue;
    }
    if (Array.isArray(raw)) {
      const values = raw
        .map((value) => String(value))
        .map((value) => value.trim())
        .filter(Boolean);
      if (values.length) {
        normalised[dimension] = values;
      }
      continue;
    }
    if (raw === null || raw === undefined) {
      continue;
    }
    const value = String(raw).trim();
    if (value) {
      normalised[dimension] = [value];
    }
  }
  return normalised;
};

const invertAliasesMap = (aliases: Record<string, unknown> | undefined | null): Record<string, string[]> => {
  if (!aliases || typeof aliases !== "object") {
    return {};
  }
  const map: Record<string, string[]> = {};
  for (const [aliasRaw, columnRaw] of Object.entries(aliases)) {
    if (typeof columnRaw !== "string") {
      continue;
    }
    const alias = aliasRaw.trim();
    const column = columnRaw.trim();
    if (!alias || !column) {
      continue;
    }
    if (!map[column]) {
      map[column] = [];
    }
    if (!map[column].includes(alias)) {
      map[column].push(alias);
    }
  }
  for (const key of Object.keys(map)) {
    map[key] = map[key].sort((a, b) => a.localeCompare(b));
  }
  return map;
};

const buildDefaultEndpoints = (run: string, artifactsRoot?: string): Required<EndpointOverrides> => {
  const ar = artifactsRoot && artifactsRoot.trim() ? `&artifacts_root=${encodeURIComponent(artifactsRoot)}` : "";
  const runParam = run && run.trim() ? `run=${encodeURIComponent(run)}` : "";
  const qp = (base: string) => `${base}${runParam ? `?${runParam}${ar}` : ar ? `?${ar.slice(1)}` : ""}`;
  return {
    metrics: qp(`${DEFAULT_BASE}/metrics`),
    dimensions: qp(`${DEFAULT_BASE}/dimensions`),
    insights: qp(`${DEFAULT_BASE}/insights`),
    dataset: qp(`${DEFAULT_BASE}/orders`),
    correlations: qp(`${DEFAULT_BASE}/correlations`) + (qp(`${DEFAULT_BASE}/correlations`).includes("?") ? "&" : "?") + "top=50",
    intelligence: qp(`${DEFAULT_BASE}/intelligence`),
    catalog: qp(`${DEFAULT_BASE}/kpi-catalog`),
    knime: qp(`${DEFAULT_BASE}/knime-data`) + (qp(`${DEFAULT_BASE}/knime-data`).includes("?") ? "&" : "?") + "limit=250",
    knimeReport: qp(`${DEFAULT_BASE}/knime-report`),
  };
};

const fetchJson = async <T,>(url: string | undefined, fallback: T): Promise<T> => {
  if (!url) {
    return fallback;
  }
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    console.warn("[story-bi] falling back for", url, error);
    return fallback;
  }
};

const fetchDataset = async (url: string | undefined, fallback: BiDatasetRow[]): Promise<BiDatasetRow[]> => {
  if (!url) {
    return fallback;
  }
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    const data = await response.json();
    // Handle the specific structure returned by the API
    if (data && data.rows && Array.isArray(data.rows)) {
      return data.rows as BiDatasetRow[];
    }
    // If it's already an array, return it
    if (Array.isArray(data)) {
      return data as BiDatasetRow[];
    }
    throw new Error("Invalid dataset format received from API");
  } catch (error) {
    console.warn("[story-bi] falling back for dataset", url, error);
    return fallback;
  }
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const normaliseMetricsPayload = (payload: unknown) => {
  if (Array.isArray(payload)) {
    return { metrics: payload as MetricSpec[], metadata: {} as Record<string, unknown> };
  }
  if (isRecord(payload)) {
    const metrics = Array.isArray(payload.metrics) ? (payload.metrics as MetricSpec[]) : [];
    const metadata =
      isRecord(payload.metadata)
        ? (payload.metadata as Record<string, unknown>)
        : Object.fromEntries(Object.entries(payload).filter(([key]) => key !== "metrics"));
    return { metrics, metadata };
  }
  return { metrics: fallbackMetrics.length ? fallbackMetrics : [], metadata: {} as Record<string, unknown> };
};

const normaliseDimensionsPayload = (payload: unknown) => {
  if (isRecord(payload) && Array.isArray(payload.date) && Array.isArray(payload.numeric) && Array.isArray(payload.categorical)) {
    const catalog: DimensionsCatalog = {
      generated_at: typeof payload.generated_at === "string" ? payload.generated_at : undefined,
      row_count: typeof payload.row_count === "number" ? payload.row_count : undefined,
      date: payload.date as DimensionsCatalog["date"],
      numeric: payload.numeric as DimensionsCatalog["numeric"],
      categorical: payload.categorical as DimensionsCatalog["categorical"],
      bool: Array.isArray(payload.bool) ? (payload.bool as DimensionsCatalog["bool"]) : [],
    };
    const metadata = isRecord(payload.metadata)
      ? (payload.metadata as Record<string, unknown>)
      : Object.fromEntries(
          Object.entries(payload).filter(
            ([key]) => !["generated_at", "row_count", "date", "numeric", "categorical", "bool"].includes(key),
          ),
        );
    return { catalog, metadata };
  }
  return {
    catalog: fallbackDimensions.date.length ? fallbackDimensions : EMPTY_DIMENSIONS,
    metadata: {} as Record<string, unknown>,
  };
};

const normaliseInsightsPayload = (payload: unknown) => {
  if (isRecord(payload)) {
    const insights = Array.isArray(payload.insights) ? (payload.insights as Insight[]) : [];
    const statsRaw = isRecord(payload.stats) ? (payload.stats as Record<string, unknown>) : undefined;
    const stats: InsightStats | undefined = statsRaw
      ? {
          insights_total: typeof statsRaw.insights_total === "number" ? statsRaw.insights_total : undefined,
          by_type: isRecord(statsRaw.by_type) ? (statsRaw.by_type as Record<string, number>) : undefined,
        }
      : undefined;
    const metadata: Record<string, unknown> = {};
    if (typeof payload.generated_at === "string") {
      metadata.generated_at = payload.generated_at;
    }
    if (isRecord(payload.sources)) {
      metadata.sources = payload.sources;
    }
    if (Array.isArray(payload.log)) {
      metadata.log = payload.log;
    }
    return { insights, stats, metadata };
  }
  if (Array.isArray(payload)) {
    return { insights: payload as Insight[], stats: undefined, metadata: {} as Record<string, unknown> };
  }
  return {
    insights: fallbackInsights.length ? fallbackInsights : [],
    stats: undefined,
    metadata: {} as Record<string, unknown>,
  };
};

export const BiDataProvider: React.FC<BiDataProviderProps> = ({ children, endpoints }) => {
  const [currentRun, setCurrentRun] = useState<string>(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const fromQuery = params.get("run");
      if (fromQuery && fromQuery.trim()) {
        return fromQuery.trim();
      }
      const stored = window.localStorage.getItem(RUN_STORAGE_KEY);
      if (stored && stored.trim()) {
        return stored;
      }
    }
    return DEFAULT_RUN;
  });
  const [availableRuns, setAvailableRuns] = useState<PipelineRunInfo[]>([]);
  const [runsLoading, setRunsLoading] = useState<boolean>(false);
  const [runsError, setRunsError] = useState<string | undefined>(undefined);

  const [serverArtifactsRoot, setServerArtifactsRoot] = useState<string | undefined>(undefined);

  const mergedEndpoints = useMemo(() => {
    const defaults = buildDefaultEndpoints(currentRun, serverArtifactsRoot);
    return { ...defaults, ...(endpoints ?? {}) };
  }, [currentRun, serverArtifactsRoot, endpoints]);

  const [metrics, setMetrics] = useState<MetricSpec[]>([]);
  const [dimensions, setDimensions] = useState<DimensionsCatalog>(EMPTY_DIMENSIONS);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [dataset, setDataset] = useState<BiDatasetRow[]>([]);
  const [correlations, setCorrelations] = useState<CorrelationCollection>(EMPTY_CORRELATIONS);
  const [intelligence, setIntelligence] = useState<Layer3Intelligence>(fallbackIntelligence);
  const [knimeData, setKnimeData] = useState<KnimeDataSnapshot | null>(fallbackKnimeData);
  const [knimeReport, setKnimeReport] = useState<KnimeReport | null>(fallbackKnimeReport);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | undefined>();
  const [filters, setFilters] = useState<Record<string, string[]>>({});
  const [catalogMeta, setCatalogMeta] = useState<CatalogMetadata>({});
  const [insightStats, setInsightStats] = useState<InsightStats | undefined>(undefined);
  const [schemaGlossaryRecords, setSchemaGlossaryRecords] = useState<SchemaTerminologyRecord[]>([]);
  const [schemaGlossaryAliases, setSchemaGlossaryAliases] = useState<Record<string, string[]>>({});
  const [schemaGlossaryLoading, setSchemaGlossaryLoading] = useState<boolean>(false);
  const [schemaGlossaryError, setSchemaGlossaryError] = useState<string | undefined>(undefined);

  const refreshRuns = useCallback(async () => {
    setRunsLoading(true);
    try {
      const response = await api.listRuns();
      setServerArtifactsRoot(typeof response?.artifacts_root === "string" ? response.artifacts_root : undefined);
      const sorted = (response?.runs ?? [])
        .slice()
        .sort((a, b) => {
          const aTime = a?.updated_at ? new Date(a.updated_at).getTime() : 0;
          const bTime = b?.updated_at ? new Date(b.updated_at).getTime() : 0;
          return bTime - aTime;
        });
      setAvailableRuns(sorted);
      setRunsError(undefined);
      setCurrentRun((previous) => {
        if (!sorted.length) return previous || DEFAULT_RUN;
        // honour run from URL query if present
        if (typeof window !== "undefined") {
          const q = new URLSearchParams(window.location.search).get("run");
          if (q && sorted.some((r) => r.run_id === q)) return q;
        }
        if (sorted.some((run) => run.run_id === previous)) {
          return previous;
        }
        return sorted[0].run_id;
      });
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshRuns();
  }, [refreshRuns]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(RUN_STORAGE_KEY, currentRun);
    }
  }, [currentRun]);

  useEffect(() => {
    setFilters({});
  }, [currentRun]);

  const fetchSchemaGlossary = useCallback(
    async (runId: string, artifactsRoot?: string) => {
      if (!runId || !runId.trim()) {
        setSchemaGlossaryRecords([]);
        setSchemaGlossaryAliases({});
        setSchemaGlossaryError(undefined);
        setSchemaGlossaryLoading(false);
        return;
      }
      setSchemaGlossaryLoading(true);
      setSchemaGlossaryError(undefined);
      try {
        const response = await api.getSchemaTerminology(runId, artifactsRoot);
        setSchemaGlossaryRecords(response.records ?? []);
        setSchemaGlossaryAliases(invertAliasesMap(response.aliases ?? {}));
      } catch (error) {
        console.warn("[story-bi] failed to load schema glossary", error);
        setSchemaGlossaryError(error instanceof Error ? error.message : String(error));
        setSchemaGlossaryRecords([]);
        setSchemaGlossaryAliases({});
      } finally {
        setSchemaGlossaryLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void fetchSchemaGlossary(currentRun, serverArtifactsRoot);
  }, [fetchSchemaGlossary, currentRun, serverArtifactsRoot]);

  const refreshSchemaGlossary = useCallback(async () => {
    await fetchSchemaGlossary(currentRun, serverArtifactsRoot);
  }, [fetchSchemaGlossary, currentRun, serverArtifactsRoot]);

  const handleRunChange = useCallback((runId: string) => {
    setCurrentRun(runId && runId.trim() ? runId : DEFAULT_RUN);
  }, []);

  useEffect(() => {
    let active = true;

    const load = async () => {
      setLoading(true);
      setError(undefined);
      try {
        const [
          metricsRes,
          dimensionsRes,
          insightsRes,
          datasetRes,
          correlationsRes,
          intelligenceRes,
          catalogRes,
          knimeRes,
          knimeReportRes,
        ] = await Promise.all([
          fetchJson<unknown>(mergedEndpoints.metrics, { metrics: [] }),
          fetchJson<unknown>(mergedEndpoints.dimensions, EMPTY_DIMENSIONS),
          fetchJson<unknown>(mergedEndpoints.insights, { insights: [] }),
          fetchDataset(mergedEndpoints.dataset, []),
          fetchJson<CorrelationCollection>(mergedEndpoints.correlations, EMPTY_CORRELATIONS),
          fetchJson<unknown>(mergedEndpoints.intelligence, fallbackIntelligence),
          fetchJson<KpiCatalog>(mergedEndpoints.catalog, {}),
          fetchJson<KnimeDataSnapshot>(mergedEndpoints.knime, fallbackKnimeData),
          fetchJson<KnimeReport>(mergedEndpoints.knimeReport, fallbackKnimeReport),
        ]);

        if (!active) return;

        const metricsPayload = normaliseMetricsPayload(metricsRes);
        const resolvedMetrics =
          metricsPayload.metrics.length > 0 ? metricsPayload.metrics : fallbackMetrics.length ? fallbackMetrics : [];
        const dimensionsPayload = normaliseDimensionsPayload(dimensionsRes);
        const hasDimensionSignals =
          (dimensionsPayload.catalog.categorical?.length ?? 0) +
            (dimensionsPayload.catalog.numeric?.length ?? 0) +
            (dimensionsPayload.catalog.date?.length ?? 0) >
          0;
        const resolvedDimensions = hasDimensionSignals
          ? dimensionsPayload.catalog
          : fallbackDimensions.date.length
            ? fallbackDimensions
            : EMPTY_DIMENSIONS;
        const insightsPayload = normaliseInsightsPayload(insightsRes);
        const resolvedInsights =
          insightsPayload.insights.length > 0 ? insightsPayload.insights : fallbackInsights.length ? fallbackInsights : [];
        const resolvedDatasetSource = datasetRes?.length ? clampRows(datasetRes) : clampRows(fallbackDataset);
        const resolvedDataset = normalizeCategoricalValues(resolvedDatasetSource, resolvedDimensions);

        setMetrics(resolvedMetrics);
        setDimensions(resolvedDimensions);
        setInsights(resolvedInsights);
        setDataset(resolvedDataset);
        const resolvedKnime =
          knimeRes && Array.isArray(knimeRes.columns) ? knimeRes : (fallbackKnimeData as KnimeDataSnapshot);
        setKnimeData(resolvedKnime);
        setKnimeReport(knimeReportRes ?? fallbackKnimeReport);
        setCatalogMeta({
          metrics: metricsPayload.metadata,
          dimensions: dimensionsPayload.metadata,
          insights: insightsPayload.metadata,
          kpiCatalog: catalogRes,
        });
        setInsightStats(insightsPayload.stats);
        const resolvedCorrelations =
          correlationsRes && Array.isArray(correlationsRes.numeric) && Array.isArray(correlationsRes.datetime)
            ? {
                numeric: correlationsRes.numeric ?? [],
                datetime: correlationsRes.datetime ?? [],
                business:
                  correlationsRes.business ??
                  {
                    numeric_numeric: [],
                    numeric_categorical: [],
                    categorical_categorical: [],
                  },
                sources: {
                  ...(fallbackCorrelations.sources ?? {}),
                  ...(correlationsRes.sources ?? {}),
                },
                run: correlationsRes.run ?? fallbackCorrelations.run ?? "run-latest",
                artifacts_root: correlationsRes.artifacts_root ?? fallbackCorrelations.artifacts_root ?? null,
                top: correlationsRes.top ?? fallbackCorrelations.top ?? null,
              }
            : fallbackCorrelations;
        setCorrelations(resolvedCorrelations);
        const parsedIntelligence = layer3IntelligenceSchema.safeParse(intelligenceRes);
        setIntelligence(parsedIntelligence.success ? parsedIntelligence.data : fallbackIntelligence);
      } catch (err) {
        if (!active) return;
        const message = err instanceof Error ? err.message : "تعذر تحميل بيانات الـ BI";
        setError(message);
        setMetrics(fallbackMetrics.length ? fallbackMetrics : []);
        setDimensions(fallbackDimensions.date.length ? fallbackDimensions : EMPTY_DIMENSIONS);
        setInsights(fallbackInsights.length ? fallbackInsights : []);
        setDataset(clampRows(fallbackDataset));
        setCorrelations(fallbackCorrelations);
        setIntelligence(fallbackIntelligence);
        setKnimeData(fallbackKnimeData);
        setKnimeReport(fallbackKnimeReport);
        setCatalogMeta({});
        setInsightStats(undefined);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      active = false;
    };
  }, [mergedEndpoints]);

  const runLayer2Assistant = useCallback(
    async (request: Layer2AgentRequest): Promise<Layer2AgentResult> => {
      const payload = {
        run: request.run ?? currentRun,
        question: request.question,
        filters: request.filters ?? filters,
        history: (request.history ?? []).map((message) => ({
          role: message.role,
          content: message.content,
        })),
      };

      let response: Response;
      try {
        response = await fetch(`${DEFAULT_BASE}/layer2/assistant`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } catch (error) {
        throw new Error(`Layer2 assistant request failed: ${(error as Error).message}`);
      }

      if (!response.ok) {
        const detail = await response.text().catch(() => response.statusText);
        throw new Error(`Layer2 assistant request failed (${response.status}): ${detail}`);
      }

      const data = (await response.json()) as Layer2AgentResponseRaw;
      const rawRecommendation = data.recommendation ?? {};
      const recommendation: Layer2AgentRecommendation = {
        metricId: rawRecommendation.metric_id ?? null,
        metricLabel: rawRecommendation.metric_label ?? null,
        dimension: rawRecommendation.dimension ?? null,
        chart: rawRecommendation.chart ?? null,
        filters: normaliseAgentFilters(
          (rawRecommendation.filters ?? undefined) as Record<string, unknown> | undefined,
        ),
        rationale: rawRecommendation.rationale ?? null,
        language: rawRecommendation.language ?? null,
        confidence: rawRecommendation.confidence ?? null,
      };

      return {
        reply: data.reply ?? "",
        recommendation,
        provider: data.provider ?? "unknown",
        model: data.model ?? "unknown",
        tokensIn: data.tokens_in ?? 0,
        tokensOut: data.tokens_out ?? 0,
        costEstimate: data.cost_estimate ?? undefined,
        durationSeconds: data.duration_s ?? undefined,
        usedFallback: Boolean(data.used_fallback),
        context: data.context,
      };
    },
    [filters, currentRun],
  );

  const value = useMemo<BiDataContextValue>(
    () => ({
      runId: currentRun,
      setRunId: handleRunChange,
      availableRuns,
      runsLoading,
      runsError,
      refreshRuns,
      metrics,
      dimensions,
      insights,
      dataset,
      correlations,
      intelligence,
      knimeData,
      knimeReport,
      loading,
      error,
      filters,
      insightStats,
      catalogMeta,
      schemaGlossary: {
        records: schemaGlossaryRecords,
        aliases: schemaGlossaryAliases,
        loading: schemaGlossaryLoading,
        error: schemaGlossaryError,
      },
      refreshSchemaGlossary,
      setFilter: (dimension: string, values: string[]) => {
        const nextValues = values.filter(Boolean);
        setFilters((prev) => {
          const updated = nextValues.length
            ? {
                ...prev,
                [dimension]: nextValues,
              }
            : Object.fromEntries(Object.entries(prev).filter(([key]) => key !== dimension));
          console.info("[story-bi] filter changed", dimension, nextValues);
          console.count("[story-bi] filter change");
          return updated;
        });
      },
      runLayer2Assistant,
    }),
    [
      currentRun,
      handleRunChange,
      availableRuns,
      runsLoading,
      runsError,
      refreshRuns,
      metrics,
      dimensions,
      insights,
      dataset,
      correlations,
      intelligence,
      knimeData,
      knimeReport,
      loading,
      error,
       filters,
       insightStats,
       catalogMeta,
       schemaGlossaryRecords,
       schemaGlossaryAliases,
       schemaGlossaryLoading,
       schemaGlossaryError,
       refreshSchemaGlossary,
       runLayer2Assistant,
     ],
   );

  return <BiDataContext.Provider value={value}>{children}</BiDataContext.Provider>;
};

export const useBiDataContext = (): BiDataContextValue => {
  const context = useContext(BiDataContext);
  if (!context) {
    throw new Error("useBiDataContext must be used within a BiDataProvider");
  }
  return context;
};
