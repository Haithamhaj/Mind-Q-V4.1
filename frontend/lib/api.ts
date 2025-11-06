const CLIENT_DEFAULT_API_BASE_URL = "/api/mindq"
const API_BASE_URL =
  (process.env.NEXT_PUBLIC_API_BASE_URL || process.env.API_BASE_URL || "").replace(/\/$/, "") ||
  CLIENT_DEFAULT_API_BASE_URL

export interface UploadResponse {
  originalName: string
  storedFileName: string
  path: string
  size: number
}

export interface PhaseRequest {
  inputs?: Record<string, unknown>
  config?: Record<string, unknown>
  artifacts_root?: string
  use_defaults?: boolean
}

export interface IngestionRequest {
  data_files: string[]
  sla_files?: string[]
  artifacts_root?: string
  config?: Record<string, unknown>
  ingestion_overrides?: Record<string, unknown>
}

export interface PipelineRequest {
  data_files: string[]
  sla_files?: string[]
  artifacts_root?: string
  stop_on_error?: boolean
  llm_credentials_file?: string
  llm_summary?: boolean
}

export interface PipelineResponse {
  run_id: string
  phases: Array<Record<string, unknown>>
}

export type PipelinePhaseStatus = "pending" | "running" | "completed" | "skipped" | "deferred"

export interface PipelineProgressPhase {
  id: string
  label: string
  status: PipelinePhaseStatus
  index: number
}

export interface AsyncJobInfo {
  id: string
  phase: string
  status: "waiting_for_user" | "processing" | "completed" | "failed"
  mode: string
  queued_at: string
  resume_endpoint: string
  artifacts_root: string
  request: Record<string, unknown>
  instructions: string[]
  manifest: string
}

export interface PipelineProgress {
  run_id?: string
  status: "running" | "completed" | "failed" | "completed_with_deferred"
  current_phase?: string | null
  completed_count: number
  total_count: number
  percent_complete: number
  phases: PipelineProgressPhase[]
  updated_at: string
  skipped?: string[]
  error?: string
  deferred?: string[]
  async_jobs?: Record<string, AsyncJobInfo>
}

export interface BiMartPreview {
  mart?: string
  view?: string
  file?: string
  row_count?: number | null
  preview?: Array<Record<string, unknown>>
}

export interface BiSemanticPayload {
  timezone?: string
  currency?: string
  marts?: Array<Record<string, unknown>>
  metrics?: Array<Record<string, unknown>>
  [key: string]: unknown
}

export interface BiLlmState {
  enabled: boolean
  providers: Record<string, boolean>
}

export interface BiPhaseResponse {
  status: string
  run_id: string
  artifacts_root: string
  semantic: BiSemanticPayload
  marts: BiMartPreview[]
  llm_enabled: boolean
  llm: BiLlmState
  builder?: Record<string, unknown>
}

export interface PipelineRunInfo {
  run_id: string
  path: string
  updated_at: string
}

export interface RunListResponse {
  artifacts_root: string
  runs: PipelineRunInfo[]
}

export interface ArtifactFileInfo {
  name: string
  path: string
  size: number
  updated_at: string
}

export interface ArtifactPhaseInfo {
  id: string
  label: string
  files: ArtifactFileInfo[]
}

export interface RunArtifactsResponse {
  run_id: string
  artifacts_root: string
  phases: ArtifactPhaseInfo[]
}

export interface RunTimelinePhaseDefinition {
  id: string
  name: Record<string, string>
  description: Record<string, string>
  expected_inputs: Array<{
    id: string
    name: Record<string, string>
    description: Record<string, string>
  }>
  expected_outputs: string[]
  key_checks: string[]
  common_failures: string[]
  learning_resources: Array<{ title: string; url?: string | null }>
}

export interface RunTimelinePhase {
  id: string
  stage_directory: string
  definition: RunTimelinePhaseDefinition
  meta?: Record<string, unknown> | null
  events: Array<Record<string, unknown>>
}

export interface RunTimelineSummary {
  status_counts: Record<string, number>
  phases_with_errors: string[]
  phases_with_warnings: string[]
  started_at?: string
  finished_at?: string
  duration_seconds?: number
}

export interface RunTimeline {
  run_id: string
  artifacts_root: string
  summary: RunTimelineSummary
  phases: RunTimelinePhase[]
}

export interface SchemaTerminologyRecord {
  column_id: string
  original_name?: string | null
  display_en?: string | null
  display_ar?: string | null
  description_en?: string | null
  description_ar?: string | null
  synonyms_en?: string[] | null
  synonyms_ar?: string[] | null
  tags?: string[] | null
  is_kpi?: boolean | null
  kpi_links?: string[] | null
  value_examples?: Array<string | number> | null
  dtype?: string | null
  null_fraction?: number | null
  unique_count?: number | null
}

export interface SchemaTerminologyResponse {
  run_id: string
  artifacts_root: string
  records: SchemaTerminologyRecord[]
  aliases: Record<string, string>
}

export interface ArtifactContentResponse {
  run_id: string
  path: string
  content_type: string
  content: unknown
}

export interface BiMetricResponse {
  run_id: string
  metric: Record<string, unknown>
  data: Array<Record<string, unknown>>
  artifacts_root: string
  timezone?: string
  currency?: string
}

export interface BiCorrelationExplainRequest {
  run: string
  feature_a: string
  feature_b: string
  kind?: string | null
  language?: "ar" | "en"
  use_llm?: boolean
  force_refresh?: boolean
  provider?: string | null
  model?: string | null
  temperature?: number | null
  max_tokens?: number | null
}

export interface BiCorrelationExplanation {
  summary?: string
  recommended_actions?: string[]
  confidence?: string | null
  mode?: string | null
  provider?: string | null
  model?: string | null
  generated_at?: string | null
  tokens_in?: number | null
  tokens_out?: number | null
  cost_estimate?: number | null
  duration_s?: number | null
  language?: string | null
  correlation?: number | null
  run?: string | null
  feature_a?: string | null
  feature_b?: string | null
  kind?: string | null
  context?: Record<string, unknown> | null
  [key: string]: unknown
}

export interface BiCorrelationExplainResponse {
  run: string
  feature_a: string
  feature_b: string
  kind: string
  correlation?: number | null
  record: Record<string, unknown>
  explanation: BiCorrelationExplanation
}

export type BusinessLayer = "operational" | "commercial" | "financial" | "general"

export interface ChartExplainRequest {
  chart_title: string
  chart_type?: string
  data_summary?: string | null
  business_layer?: BusinessLayer | null
  language?: "ar" | "en"
  use_llm?: boolean
  provider?: string | null
  model?: string | null
  temperature?: number | null
  max_tokens?: number | null
}

export interface ChartExplainResponse {
  explanation: string
  mode: "llm" | "fallback" | "fallback_after_error"
  chart_title?: string
  chart_type?: string
  business_layer?: BusinessLayer
  provider?: string
  model?: string
  tokens_in?: number
  tokens_out?: number
  cost_estimate?: number
  duration_s?: number
  error?: string
  [key: string]: unknown
}

export interface SlaAssistantMessage {
  role: "user" | "assistant"
  content: string
}

export interface SlaAssistantRequest {
  run?: string
  question: string
  history?: SlaAssistantMessage[]
  provider?: string | null
  model?: string | null
  temperature?: number
  max_tokens?: number
}

export interface SlaAssistantResponse {
  reply: Record<string, unknown>
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost_estimate: number
  duration_s: number
  context?: Record<string, unknown>
  [key: string]: unknown
}

export interface RawMetricsMessage {
  role: "user" | "assistant"
  content: string
}

export interface RawMetricsLLMRequest {
  run?: string
  top?: number
  question: string
  history?: RawMetricsMessage[]
  provider?: string | null
  model?: string | null
  temperature?: number
  max_tokens?: number
}

export interface RawMetricsLLMResponse {
  reply: Record<string, unknown>
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost_estimate: number
  duration_s: number
  metrics: Record<string, unknown>
  [key: string]: unknown
}

export interface Layer2AssistantMessage {
  role: "user" | "assistant"
  content: string
}

export interface Layer2AssistantRequest {
  run?: string
  question: string
  filters?: Record<string, string[]>
  history?: Layer2AssistantMessage[]
  provider?: string | null
  model?: string | null
  temperature?: number
  max_tokens?: number
  top_p?: number
}

export interface Layer2AssistantResponse {
  reply: string
  recommendation?: Record<string, unknown>
  provider: string
  model: string
  tokens_in: number
  tokens_out: number
  cost_estimate: number
  duration_s: number
  context?: Record<string, unknown>
  used_fallback: boolean
  [key: string]: unknown
}

class MindQAPI {
  private baseURL: string
  private biQueryCache: Map<string, { rows: Array<Record<string, unknown>>; n: number; ts: number }>

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL || CLIENT_DEFAULT_API_BASE_URL
    this.biQueryCache = new Map()
  }

  private buildURL(path: string) {
    const normalizedBase = this.baseURL.replace(/\/$/, "")
    if (path.startsWith("/")) {
      return `${normalizedBase}${path}`
    }
    return `${normalizedBase}/${path}`
  }

  private buildQueryString(params: Record<string, string | number | boolean | null | undefined>) {
    const search = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === "") {
        continue
      }
      search.append(key, String(value))
    }
    const query = search.toString()
    return query ? `?${query}` : ""
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    const contentType = response.headers.get("content-type") || ""

    if (!response.ok) {
      let errorMessage = `Request failed with ${response.status} ${response.statusText}`

      if (contentType.includes("application/json")) {
        try {
          const data = (await response.json()) as Record<string, unknown>
          if (data && typeof data === "object") {
            if (typeof data.detail === "string") {
              errorMessage = data.detail
            } else if (Array.isArray(data.detail)) {
              const detail = data.detail
                .map((item) => {
                  if (item && typeof item === "object") {
                    const location = Array.isArray(item.loc) ? item.loc.join(".") : ""
                    const message = typeof item.msg === "string" ? item.msg : ""
                    return [location, message].filter(Boolean).join(": ")
                  }
                  return ""
                })
                .filter(Boolean)
                .join("; ")
              if (detail) {
                errorMessage = detail
              }
            }
          }
        } catch {
          // ignore JSON parse failures and fallback to default message
        }
      } else {
        try {
          const text = await response.text()
          if (text.trim()) {
            errorMessage = text.trim()
          }
        } catch {
          // ignore text parse failures
        }
      }

      throw new Error(errorMessage)
    }

    if (contentType.includes("application/json")) {
      return (await response.json()) as T
    }

    return undefined as T
  }

  private async get<T>(path: string): Promise<T> {
    const response = await fetch(this.buildURL(path), {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    })

    return this.handleResponse<T>(response)
  }

  private async post<T>(path: string, payload?: unknown): Promise<T> {
    const headers: HeadersInit = {
      Accept: "application/json",
    }
    let body: string | undefined
    if (payload !== undefined) {
      headers["Content-Type"] = "application/json"
      body = JSON.stringify(payload)
    }
    const response = await fetch(this.buildURL(path), {
      method: "POST",
      headers,
      body,
    })

    return this.handleResponse<T>(response)
  }

  async healthCheck(): Promise<Record<string, unknown>> {
    return this.get("/healthz")
  }

  async uploadFile(file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append("file", file)

    const response = await fetch("/api/uploads", {
      method: "POST",
      body: formData,
    })

    return this.handleResponse<UploadResponse>(response)
  }

  async getBiMetrics(run?: string): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run })
    return this.get(`/api/bi/metrics${query}`)
  }

  async getBiKpiCatalog(run?: string): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run })
    return this.get(`/api/bi/kpi-catalog${query}`)
  }

  async getBiDimensions(run?: string): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run })
    return this.get(`/api/bi/dimensions${query}`)
  }

  async getBiInsights(run?: string): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run })
    return this.get(`/api/bi/insights${query}`)
  }

  async getBiCorrelations(run?: string, top?: number): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run, top })
    return this.get(`/api/bi/correlations${query}`)
  }

  async explainBiChart(request: ChartExplainRequest): Promise<ChartExplainResponse> {
    return this.post(`/api/bi/charts/explain`, request)
  }

  async getSlaSummary(run?: string): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run })
    return this.get(`/api/bi/sla${query}`)
  }

  async getSlaSop(run?: string): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run })
    return this.get(`/api/bi/sla/sop${query}`)
  }

  async getSlaGapAnalysis(run?: string): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run })
    return this.get(`/api/bi/sla/gap-analysis${query}`)
  }

  async getBiData(run?: string, limit?: number): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run, limit })
    return this.get(`/api/bi/data${query}`)
  }

  async converseSlaAssistant(request: SlaAssistantRequest): Promise<SlaAssistantResponse> {
    return this.post(`/api/bi/sla/assistant`, request)
  }

  async getRawMetrics(run?: string, top?: number): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run, top })
    return this.get(`/api/bi/metrics/raw${query}`)
  }

  async converseRawMetrics(request: RawMetricsLLMRequest): Promise<RawMetricsLLMResponse> {
    return this.post(`/api/bi/metrics/raw/llm`, request)
  }

  async getKnimeData(
    run?: string,
    options: { limit?: number; offset?: number } = {},
  ): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run, limit: options.limit, offset: options.offset })
    return this.get(`/api/bi/knime-data${query}`)
  }

  async getKnimeReport(run?: string): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run })
    return this.get(`/api/bi/knime-report${query}`)
  }

  async getIntelligence(run?: string): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run })
    return this.get(`/api/bi/intelligence${query}`)
  }

  async getOrders(run?: string, limit?: number): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ run, limit })
    return this.get(`/api/bi/orders${query}`)
  }

  async converseLayer2Assistant(request: Layer2AssistantRequest): Promise<Layer2AssistantResponse> {
    return this.post(`/api/bi/layer2/assistant`, request)
  }

  async runPhase01(runId: string, request: IngestionRequest): Promise<Record<string, unknown>> {
    return this.post(`/v1/runs/${runId}/phases/01/ingestion`, request)
  }

  async runPhase(runId: string, phase: string, request: PhaseRequest): Promise<Record<string, unknown>> {
    const phaseMap: Record<string, string> = {
      "02": "quality",
      "03": "schema",
      "04": "profile",
      "05": "missing",
      "06": "standardize",
      "07": "readiness",
      "08": "insights",
      "09": "business-validation",
      "10": "bi",
    }

    const endpoint = phaseMap[phase]
    if (!endpoint) {
      throw new Error(`Invalid phase: ${phase}`)
    }

    return this.post(`/v1/runs/${runId}/phases/${phase}/${endpoint}`, request)
  }

  async runPhase10(runId: string, request: PhaseRequest = {}): Promise<BiPhaseResponse> {
    return this.post(`/v1/runs/${runId}/phases/10/bi`, request)
  }

  async getBiMeta(runId: string, artifactsRoot?: string): Promise<Record<string, unknown>> {
    const query = artifactsRoot ? `?artifacts_root=${encodeURIComponent(artifactsRoot)}` : ""
    return this.get(`/v1/bi/${runId}/meta${query}`)
  }

  async biQuery(
    runId: string,
    sql: string,
    options?: { artifacts_root?: string; timezone?: string; currency?: string; llm_enabled?: boolean },
  ): Promise<{ rows: Array<Record<string, unknown>>; n: number }> {
    const payload = { sql, ...(options ?? {}) }
    const key = JSON.stringify({ runId, sql, options })
    const now = Date.now()
    const ttlMs = 60_000
    const cached = this.biQueryCache.get(key)
    if (cached && now - cached.ts < ttlMs) {
      return { rows: cached.rows, n: cached.n }
    }
    const result = await this.post<{ rows: Array<Record<string, unknown>>; n: number }>(
      `/v1/bi/${runId}/query`,
      payload,
    )
    this.biQueryCache.set(key, { ...result, ts: now })
    return result
  }

  async biPlan(
    runId: string,
    question: string,
    options?: { artifacts_root?: string; timezone?: string; currency?: string; llm_enabled?: boolean },
  ): Promise<{ plan: Record<string, unknown>; data: Array<Record<string, unknown>> }> {
    const payload = { question, ...(options ?? {}) }
    return this.post(`/v1/bi/${runId}/llm-plan`, payload)
  }

  async runFeatureReport(runId: string, request: PhaseRequest): Promise<Record<string, unknown>> {
    return this.post(`/v1/runs/${runId}/phases/07/feature-report`, request)
  }

  async runLLMSummary(runId: string, request: PhaseRequest): Promise<Record<string, unknown>> {
    return this.post(`/v1/runs/${runId}/phases/07/llm-summary`, request)
  }

  async runBusinessCorrelations(runId: string, request: PhaseRequest): Promise<Record<string, unknown>> {
    return this.post(`/v1/runs/${runId}/phases/07/business-correlations`, request)
  }

  async runKnimeBridge(runId: string, request: PhaseRequest = { use_defaults: true }): Promise<Record<string, unknown>> {
    return this.post(`/v1/runs/${runId}/phases/07/knime-bridge`, request)
  }

  async runFullPipeline(
    runId: string,
    request: PipelineRequest,
    options?: { asyncMode?: boolean },
  ): Promise<PipelineResponse | null> {
    const query = options?.asyncMode ? "?async_mode=true" : ""
    const response = await fetch(this.buildURL(`/v1/runs/${runId}/pipeline/full${query}`), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(request),
    })

    if (response.status === 202) {
      // Pipeline accepted for asynchronous processing
      return null
    }

    return this.handleResponse<PipelineResponse>(response)
  }

  async runCausalPhase(
    runId: string,
    options: { problem_name?: string } = {},
  ): Promise<Record<string, unknown>> {
    const query = this.buildQueryString({ problem_name: options.problem_name })
    return this.post(`/v1/runs/${runId}/phases/09_5_causal${query}`)
  }

  async listRuns(artifactsRoot?: string): Promise<RunListResponse> {
    const query = artifactsRoot ? `?artifacts_root=${encodeURIComponent(artifactsRoot)}` : ""
    return this.get(`/v1/runs${query}`)
  }

  async listRunArtifacts(runId: string, artifactsRoot?: string): Promise<RunArtifactsResponse> {
    const query = artifactsRoot ? `?artifacts_root=${encodeURIComponent(artifactsRoot)}` : ""
    return this.get(`/v1/runs/${runId}/artifacts${query}`)
  }

  async getRunTimeline(runId: string, artifactsRoot?: string): Promise<RunTimeline> {
    const query = artifactsRoot ? `?artifacts_root=${encodeURIComponent(artifactsRoot)}` : ""
    return this.get(`/v1/runs/${runId}/timeline${query}`)
  }

  async getSchemaTerminology(
    runId: string,
    artifactsRoot?: string,
    format: "json" | "flat" = "flat",
  ): Promise<SchemaTerminologyResponse> {
    const params = new URLSearchParams({ format })
    if (artifactsRoot) {
      params.set("artifacts_root", artifactsRoot)
    }
    return this.get(`/v1/runs/${runId}/schema/terminology?${params.toString()}`)
  }

  async getPipelineStatus(runId: string, artifactsRoot?: string): Promise<PipelineProgress> {
    const query = artifactsRoot ? `?artifacts_root=${encodeURIComponent(artifactsRoot)}` : ""
    return this.get(`/v1/runs/${runId}/pipeline/status${query}`)
  }

  async getBiMetric(runId: string, metricId: string, artifactsRoot?: string): Promise<BiMetricResponse> {
    const query = artifactsRoot ? `?artifacts_root=${encodeURIComponent(artifactsRoot)}` : ""
    return this.get(`/v1/bi/${runId}/metrics/${encodeURIComponent(metricId)}${query}`)
  }

  async explainBiCorrelation(request: BiCorrelationExplainRequest): Promise<BiCorrelationExplainResponse> {
    return this.post(`/api/bi/correlations/explain`, request)
  }

  async getArtifactContent(runId: string, path: string, artifactsRoot?: string): Promise<ArtifactContentResponse> {
    const params = new URLSearchParams({ path })
    if (artifactsRoot) {
      params.set("artifacts_root", artifactsRoot)
    }
    return this.get(`/v1/runs/${runId}/artifacts/content?${params.toString()}`)
  }
}

export const api = new MindQAPI()
