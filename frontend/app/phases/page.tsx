"use client"

import type React from "react"

import { useMemo, useRef, useState } from "react"
import { Sidebar } from "@/components/sidebar"
import { Header } from "@/components/header"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { AlertTriangle, Loader2, Play, Plus, Sparkles, X } from "lucide-react"
import { api, type BiPhaseResponse, type PhaseRequest } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"
import { VisualizationAdapter } from "@/components/VisualizationAdapter"
import { useLanguage } from "@/context/language-context"

const phases = [
  { id: "01", name: "Ingestion", desc: "Multi-file CSV/Parquet ingestion and SLA processing" },
  { id: "02", name: "Quality", desc: "Quality gates, issue catalogues, and baselines" },
  { id: "03", name: "Schema", desc: "Schema extraction and drift detection" },
  { id: "03.5", name: "TextOps", desc: "Arabic/English text normalization, PII masking, and NLP features" },
  { id: "04", name: "Profile", desc: "Lightweight profiling and row-count consistency" },
  { id: "05", name: "Missing", desc: "Hybrid and groupwise imputation with PSI monitoring" },
  { id: "06", name: "Standardize", desc: "Feature standardisation and column protection" },
  { id: "07", name: "Readiness", desc: "Leakage detection, correlation, and NZV analysis" },
  { id: "08", name: "Insights", desc: "Operational insights, diagnostics, and narrative cards" },
  { id: "09", name: "Validation", desc: "Business/SLA validation, exports, and decisions" },
  { id: "10", name: "BI Delivery", desc: "Semantic marts, metrics.yaml, and BI assistant" },
]

const generateRunId = () => `phase-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`

export default function PhasesPage(): React.JSX.Element {
  const initialRunId = useMemo(() => generateRunId(), [])
  const { translate } = useLanguage()
  const [selectedPhase, setSelectedPhase] = useState("01")
  const [runId, setRunId] = useState(initialRunId)
  const [dataFiles, setDataFiles] = useState<string[]>([])
  const [slaFiles, setSlaFiles] = useState<string[]>([])
  const [configJson, setConfigJson] = useState("")
  const [isRunning, setIsRunning] = useState(false)
  const [phaseResult, setPhaseResult] = useState<Record<string, unknown> | null>(null)
  const [phaseError, setPhaseError] = useState<string | null>(null)
  const [isUploadingDataFiles, setIsUploadingDataFiles] = useState(false)
  const [isUploadingSlaFiles, setIsUploadingSlaFiles] = useState(false)
  const [biChartData, setBiChartData] = useState<Array<Record<string, unknown>> | null>(null)
  const [biChartMeta, setBiChartMeta] = useState<
    | { title: string; chartType: string; xKey: string; valueKey: string; description?: string; metricId?: string }
    | null
  >(null)
  const [pendingMetricId, setPendingMetricId] = useState<string | null>(null)
  const [isRunningBiQuery, setIsRunningBiQuery] = useState(false)
  const [biLlmQuestion, setBiLlmQuestion] = useState("")
  const [biLlmResult, setBiLlmResult] = useState<
    | { plan: Record<string, unknown>; data: Array<Record<string, unknown>> }
    | null
  >(null)
  const [isRunningBiPlan, setIsRunningBiPlan] = useState(false)
  const [isExplainingChart, setIsExplainingChart] = useState(false)
  const [biResult, setBiResult] = useState<BiPhaseResponse | null>(null)
  const { toast } = useToast()

  const dataFileInputRef = useRef<HTMLInputElement>(null)
  const slaFileInputRef = useRef<HTMLInputElement>(null)

  const addDataFile = () => dataFileInputRef.current?.click()
  const addManualDataFile = () => setDataFiles((prev) => [...prev, ""])
  const handleDataFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return
    setIsUploadingDataFiles(true)
    try {
      const uploads = await Promise.all(Array.from(files).map((file) => api.uploadFile(file)))
      setDataFiles((prev) => [...prev, ...uploads.map((upload) => upload.path)])
      toast({
        title: "Data ready",
        description: `Uploaded ${uploads.length} file${uploads.length > 1 ? "s" : ""} for ingestion.`,
      })
    } catch (error) {
      console.error("[phases] data upload failed:", error)
      toast({
        title: "Upload failed",
        description: error instanceof Error ? error.message : "Could not upload data files.",
        variant: "destructive",
      })
    } finally {
      setIsUploadingDataFiles(false)
      if (dataFileInputRef.current) dataFileInputRef.current.value = ""
    }
  }

  const removeDataFile = (index: number) => setDataFiles((prev) => prev.filter((_, i) => i !== index))
  const updateDataFile = (index: number, value: string) =>
    setDataFiles((prev) => {
      const updated = [...prev]
      updated[index] = value
      return updated
    })

  const addSlaFile = () => slaFileInputRef.current?.click()
  const addManualSlaFile = () => setSlaFiles((prev) => [...prev, ""])

  const handleSlaFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files
    if (!files || files.length === 0) return
    setIsUploadingSlaFiles(true)
    try {
      const uploads = await Promise.all(Array.from(files).map((file) => api.uploadFile(file)))
      setSlaFiles((prev) => [...prev, ...uploads.map((upload) => upload.path)])
      toast({
        title: "SLA ready",
        description: `Uploaded ${uploads.length} SLA document${uploads.length > 1 ? "s" : ""}.`,
      })
    } catch (error) {
      console.error("[phases] SLA upload failed:", error)
      toast({
        title: "Upload failed",
        description: error instanceof Error ? error.message : "Could not upload SLA files.",
        variant: "destructive",
      })
    } finally {
      setIsUploadingSlaFiles(false)
      if (slaFileInputRef.current) slaFileInputRef.current.value = ""
    }
  }

  const removeSlaFile = (index: number) => setSlaFiles((prev) => prev.filter((_, i) => i !== index))
  const updateSlaFile = (index: number, value: string) =>
    setSlaFiles((prev) => {
      const updated = [...prev]
      updated[index] = value
      return updated
    })

  const parseConfig = (): Record<string, unknown> | undefined => {
    if (!configJson.trim()) return undefined
    try {
      return JSON.parse(configJson)
    } catch {
      toast({
        title: "Invalid JSON",
        description: "Advanced configuration must be valid JSON.",
        variant: "destructive",
      })
      return undefined
    }
  }

  const handleRunPhase = async () => {
    const trimmedRunId = runId.trim() || generateRunId()
    if (!runId.trim()) setRunId(trimmedRunId)

    const config = parseConfig()
    if (configJson.trim() && !config) return

    if (selectedPhase === "10") {
      setBiChartData(null)
      setBiChartMeta(null)
      setBiLlmResult(null)
      setPendingMetricId(null)
      setBiResult(null)
    }

    setIsRunning(true)
    setPhaseResult(null)
    setPhaseError(null)

    try {
      let response: Record<string, unknown> | null = null
      if (selectedPhase === "01") {
        if (dataFiles.filter((file) => file.trim()).length === 0) {
          toast({
            title: "Validation error",
            description: "Phase 01 requires at least one data file.",
            variant: "destructive",
          })
          return
        }
        response = await api.runPhase01(trimmedRunId, {
          data_files: dataFiles.filter((file) => file.trim()),
          sla_files: slaFiles.filter((file) => file.trim()) || undefined,
          config: config,
        })
      } else {
        const request: PhaseRequest = {
          artifacts_root: config?.artifacts_root as string | undefined,
          config,
        }
        if (selectedPhase === "10") {
          const biPayload = await api.runPhase10(trimmedRunId, request)
          setPhaseResult(biPayload)
          setBiResult(biPayload)
          setBiChartData(null)
          setBiChartMeta(null)
          setBiLlmResult(null)
          return
        }
        response = await api.runPhase(trimmedRunId, selectedPhase, request)
      }
      if (response) {
        setPhaseResult(response)
      }
    } catch (error) {
      console.error("[phases] phase execution failed:", error)
      setPhaseError(error instanceof Error ? error.message : "Phase execution failed.")
      toast({
        title: "Phase failed",
        description: error instanceof Error ? error.message : "Phase execution failed.",
        variant: "destructive",
      })
    } finally {
      setIsRunning(false)
    }
  }
  const handleRunMetricPreview = async (metric: Record<string, unknown>) => {
    if (!biResult) {
      toast({
        title: "Run Phase 10 first",
        description: "Generate Stage 10 artifacts before previewing metrics.",
        variant: "destructive",
      })
      return
    }
    if (typeof metric.sql !== "string" || !metric.sql.trim()) {
      toast({
        title: "Metric has no SQL",
        description: "The selected metric definition does not provide runnable SQL.",
        variant: "destructive",
      })
      return
    }
    const metricId = String(metric.id ?? metric.name ?? metric.sql)
    setPendingMetricId(metricId)
    setIsRunningBiQuery(true)
    try {
      const response = await api.biQuery(runId, metric.sql, {
        artifacts_root: biResult.artifacts_root,
        timezone: biResult.semantic?.timezone as string | undefined,
        currency: biResult.semantic?.currency as string | undefined,
      })
      const chartType =
        typeof metric.default_chart === "string" && metric.default_chart ? (metric.default_chart as string) : "bar"
      setBiChartData(response.rows)
      setBiChartMeta({
        title: String(metric.name ?? metricId),
        chartType,
        xKey: "dt",
        valueKey: "val",
        description: typeof metric.sql === "string" ? (metric.sql as string) : undefined,
        metricId,
      })
      setBiLlmResult(null)
    } catch (error) {
      console.error("[phases] metric preview failed:", error)
      toast({
        title: "Preview failed",
        description: error instanceof Error ? error.message : "Unable to execute metric SQL.",
        variant: "destructive",
      })
    } finally {
      setPendingMetricId(null)
      setIsRunningBiQuery(false)
    }
  }

  const handleRunBiPlan = async () => {
    if (!biResult) {
      toast({
        title: "Run Phase 10 first",
        description: "Generate Stage 10 artifacts before using the assistant.",
        variant: "destructive",
      })
      return
    }
    const trimmedQuestion = biLlmQuestion.trim()
    if (!trimmedQuestion) {
      toast({
        title: "Ask a question",
        description: "Provide a business question for the BI assistant.",
        variant: "destructive",
      })
      return
    }
    setIsRunningBiPlan(true)
    try {
      const response = await api.biPlan(runId, trimmedQuestion, {
        artifacts_root: biResult.artifacts_root,
        timezone: biResult.semantic?.timezone as string | undefined,
        currency: biResult.semantic?.currency as string | undefined,
      })
      setBiLlmResult(response)
      const plan = response.plan ?? {}
      const chartType =
        typeof plan.chart_type === "string" && plan.chart_type ? (plan.chart_type as string) : "line"
      const xKey = typeof plan.xkey === "string" && plan.xkey ? (plan.xkey as string) : "dt"
      setBiChartData(response.data)
      setBiChartMeta({
        title: String(plan.metric ?? "LLM Insight"),
        chartType,
        xKey,
        valueKey: "val",
        description: typeof plan.explain_ar === "string" ? (plan.explain_ar as string) : undefined,
        metricId: String(plan.metric ?? "llm_plan"),
      })
    } catch (error) {
      console.error("[phases] BI assistant failed:", error)
      toast({
        title: "Assistant failed",
        description: error instanceof Error ? error.message : "Unable to generate a BI plan.",
        variant: "destructive",
      })
    } finally {
      setIsRunningBiPlan(false)
    }
  }

  const handleExplainChart = async () => {
    if (!biResult) {
      toast({
        title: "Run Phase 10 first",
        description: "Generate Stage 10 artifacts before using the assistant.",
        variant: "destructive",
      })
      return
    }
    // Compose a concise Arabic question with chart context
    const title = biChartMeta?.title ?? "رسم بياني"
    const chartType = biChartMeta?.chartType ?? "bar"
    const xKey = biChartMeta?.xKey ?? "dt"
    const valueKey = biChartMeta?.valueKey ?? "val"
    const metricId = biChartMeta?.metricId ?? ""
    const sampleRows = (biChartData ?? []).slice(0, 20)

    const question = [
      `اشرح الرسم التالي بشكل موجز وواضح للمستخدم غير التقني:`,
      `العنوان: ${title}`,
      `النوع: ${chartType}`,
      `المحور الأفقي (${xKey}) والمحور العمودي (${valueKey})`,
      metricId ? `المتريك: ${metricId}` : "",
      `قدّم تلخيصاً لأبرز الأنماط، القيم الشاذة، الاتجاهات، وأي نقاط يجب الانتباه لها.`,
    ]
      .filter(Boolean)
      .join("\n")

    setIsExplainingChart(true)
    try {
      const response = await api.biPlan(runId, question, {
        artifacts_root: biResult.artifacts_root,
        timezone: biResult.semantic?.timezone as string | undefined,
        currency: biResult.semantic?.currency as string | undefined,
      })
      // Prefer plan.explain_ar if present; otherwise keep full plan
      setBiLlmResult({ plan: response.plan, data: response.data })
      setBiChartData(sampleRows.length > 0 ? sampleRows : response.data)
      setBiChartMeta((prev) => ({
        title: prev?.title ?? title,
        chartType: prev?.chartType ?? chartType,
        xKey: prev?.xKey ?? xKey,
        valueKey: prev?.valueKey ?? valueKey,
        description: typeof response.plan?.explain_ar === "string" ? (response.plan.explain_ar as string) : prev?.description,
        metricId: prev?.metricId ?? metricId,
      }))
    } catch (error) {
      console.error("[phases] BI explanation failed:", error)
      toast({
        title: "Assistant failed",
        description: error instanceof Error ? error.message : "Unable to generate an explanation.",
        variant: "destructive",
      })
    } finally {
      setIsExplainingChart(false)
    }
  }

  const biLlm = biResult ? biResult.llm ?? { enabled: Boolean(biResult.llm_enabled), providers: {} } : null
  const metricDefinitions = Array.isArray(biResult?.semantic?.metrics)
    ? (biResult?.semantic?.metrics as Record<string, unknown>[])
    : []

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex w-full flex-col">
        <Header title="Phases" subtitle="Run individual phases or validate stage outputs" />

        <main className="flex-1 space-y-6 overflow-y-auto p-6">
          <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
            <Card>
              <CardHeader>
                <CardTitle>Phase Configuration</CardTitle>
                <CardDescription>Select a phase, provide inputs, and execute.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <Tabs defaultValue="phase">
                  <TabsList className="grid grid-cols-2">
                    <TabsTrigger value="phase">Phase</TabsTrigger>
                    <TabsTrigger value="advanced">Advanced</TabsTrigger>
                  </TabsList>
                  <TabsContent value="phase" className="space-y-4">
                    <div className="space-y-2">
                      <Label>Select Phase</Label>
                      <div className="flex items-center gap-2 overflow-x-auto pb-2">
                        {phases.map((phase) => (
                          <button
                            key={phase.id}
                            type="button"
                            onClick={() => setSelectedPhase(phase.id)}
                            className={`flex h-10 min-w-[80px] flex-col items-center justify-center rounded-md border px-3 text-xs ${
                              phase.id === selectedPhase
                                ? "border-primary bg-primary/10 text-primary"
                                : "border-border bg-card text-muted-foreground"
                            }`}
                          >
                            <span className="text-sm font-semibold">{phase.id}</span>
                            <span>{phase.name}</span>
                          </button>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {phases.find((phase) => phase.id === selectedPhase)?.desc}
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="runId">Run ID</Label>
                      <Input
                        id="runId"
                        value={runId}
                        onChange={(e) => setRunId(e.target.value)}
                        placeholder="Custom Run ID"
                      />
                      <p className="text-xs text-muted-foreground">Leave blank to auto-generate a run ID.</p>
                    </div>
                    {selectedPhase === "01" ? (
                      <div className="space-y-3 rounded-lg border border-border bg-muted/10 p-3">
                        <div className="flex items-center justify-between">
                          <Label>Data Files</Label>
                          <div className="flex gap-2">
                            <Button variant="outline" size="sm" onClick={addDataFile} disabled={isUploadingDataFiles}>
                              <Plus className="mr-2 h-4 w-4" />
                              Upload
                            </Button>
                            <Button variant="ghost" size="sm" onClick={addManualDataFile}>
                              Add Path
                            </Button>
                          </div>
                        </div>
                        <input
                          ref={dataFileInputRef}
                          type="file"
                          multiple
                          className="hidden"
                          onChange={handleDataFileSelect}
                        />
                        {isUploadingDataFiles ? (
                          <p className="text-xs text-muted-foreground">Uploading data files...</p>
                        ) : null}
                        {dataFiles.length > 0 ? (
                          <div className="space-y-2">
                            {dataFiles.map((file, index) => (
                              <div key={`${file}-${index}`} className="flex gap-2">
                                <Input
                                  placeholder="/absolute/path/to/file.parquet"
                                  value={file}
                                  onChange={(e) => updateDataFile(index, e.target.value)}
                                />
                                <Button variant="ghost" size="icon" onClick={() => removeDataFile(index)}>
                                  <X className="h-4 w-4" />
                                </Button>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs italic text-muted-foreground">No data files attached.</p>
                        )}
                        <p className="text-xs text-muted-foreground">
                          Uploaded files are stored under <code>uploads/</code> for ingestion.
                        </p>
                        <div className="mt-3 space-y-2">
                          <div className="flex items-center justify-between">
                            <Label>SLA Documents</Label>
                            <div className="flex gap-2">
                              <Button variant="outline" size="sm" onClick={addSlaFile} disabled={isUploadingSlaFiles}>
                                <Plus className="mr-2 h-4 w-4" />
                                Upload
                              </Button>
                              <Button variant="ghost" size="sm" onClick={addManualSlaFile}>
                                Add Path
                              </Button>
                            </div>
                          </div>
                          <input
                            ref={slaFileInputRef}
                            type="file"
                            multiple
                            className="hidden"
                            onChange={handleSlaFileSelect}
                          />
                          {isUploadingSlaFiles ? (
                            <p className="text-xs text-muted-foreground">Uploading SLA documents...</p>
                          ) : null}
                          {slaFiles.length > 0 ? (
                            <div className="space-y-2">
                              {slaFiles.map((file, index) => (
                                <div key={`${file}-${index}`} className="flex gap-2">
                                  <Input
                                    placeholder="/absolute/path/to/sla.pdf"
                                    value={file}
                                    onChange={(e) => updateSlaFile(index, e.target.value)}
                                  />
                                  <Button variant="ghost" size="icon" onClick={() => removeSlaFile(index)}>
                                    <X className="h-4 w-4" />
                                  </Button>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs italic text-muted-foreground">No SLA documents attached.</p>
                          )}
                          <p className="text-xs text-muted-foreground">
                            Formats: PDF, DOCX, CSV, HTML, Excel. Stored under <code>uploads/</code>.
                          </p>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Default inputs from previous phases will be resolved automatically. Override paths in the
                        Advanced tab if needed.
                      </p>
                    )}
                  </TabsContent>
                  <TabsContent value="advanced" className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="config">Phase Configuration (JSON)</Label>
                      <Textarea
                        id="config"
                        placeholder='{"artifacts_root": "./artifacts"}'
                        value={configJson}
                        onChange={(e) => setConfigJson(e.target.value)}
                        rows={10}
                        className="font-mono text-sm"
                      />
                      <p className="text-xs text-muted-foreground">
                        Override settings such as <code>artifacts_root</code>, <code>timezone</code>, or <code>llm_enabled</code>.
                      </p>
                    </div>
                  </TabsContent>
                  </Tabs>

                <Button
                  className="mt-2 w-full"
                  size="lg"
                  onClick={handleRunPhase}
                  disabled={isRunning || isUploadingDataFiles || isUploadingSlaFiles}
                >
                  <Play className="mr-2 h-5 w-5" />
                  {isUploadingDataFiles || isUploadingSlaFiles
                    ? "Uploading files..."
                    : isRunning
                      ? "Running Phase..."
                      : `Run Phase ${selectedPhase}`}
                </Button>
              </CardContent>
            </Card>

            <div className="space-y-6">
              {(phaseResult || phaseError) && (
                <Card>
                  <CardHeader>
                    <CardTitle>Last Phase Response</CardTitle>
                    <CardDescription>
                      {!phaseResult && phaseError ? "Phase request failed" : "Latest response payload"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {phaseError ? (
                      <div className="flex items-start gap-3 rounded-md border border-destructive/40 bg-destructive/10 p-4">
                        <AlertTriangle className="mt-0.5 h-5 w-5 text-destructive" />
                        <div>
                          <p className="font-medium text-destructive">Phase call failed</p>
                          <p className="text-sm text-destructive/80">{phaseError}</p>
                        </div>
                      </div>
                    ) : null}
                    {phaseResult ? (
                      <pre className="max-h-72 overflow-auto rounded-md border border-border bg-muted/20 p-4 text-xs text-foreground">
                        {JSON.stringify(phaseResult, null, 2)}
                      </pre>
                    ) : null}
                  </CardContent>
                </Card>
              )}
              {selectedPhase === "10" && biResult ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Stage 10 Explorer</CardTitle>
                    <CardDescription>
                      Interact with generated marts, preview metrics, and ask the BI assistant for tailored visuals.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
                      <div className="space-y-4">
                        <div className="space-y-1">
                          <p className="text-sm font-semibold text-foreground">Semantic Metrics</p>
                          <p className="text-xs text-muted-foreground">Preview metric SQL generated for this run.</p>
                        </div>
                        <div className="max-h-72 space-y-2 overflow-auto pr-1">
                          {metricDefinitions.length > 0 ? (
                            metricDefinitions.map((metric, index) => {
                              const metricId = String(metric.id ?? metric.name ?? index)
                              const active = biChartMeta?.metricId === metricId
                              const pending = pendingMetricId === metricId && isRunningBiQuery
                              return (
                                <div
                                  key={`${metricId}-${index}`}
                                  className={`space-y-2 rounded-md border p-3 text-xs ${
                                    active ? "border-primary/70 bg-primary/5" : "border-border bg-card"
                                  }`}
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <div className="space-y-0.5">
                                      <p className="text-sm font-semibold text-foreground">
                                        {String(metric.name ?? metricId)}
                                      </p>
                                      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                                        Mart: {String(metric.mart ?? "business_facts")}
                                      </p>
                                    </div>
                                    <Button
                                      size="sm"
                                      variant={active ? "secondary" : "outline"}
                                      disabled={isRunningBiQuery}
                                      onClick={() => handleRunMetricPreview(metric)}
                                    >
                                      {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Preview"}
                                    </Button>
                                  </div>
                                  <p className="line-clamp-3 text-muted-foreground">
                                    {typeof metric.sql === "string" ? metric.sql : "No SQL defined."}
                                  </p>
                                </div>
                              )
                            })
                          ) : (
                            <p className="text-xs text-muted-foreground">Semantic catalog has no metric definitions.</p>
                          )}
                        </div>
                        <div className="rounded-md border border-dashed border-border/60 p-3 text-xs text-muted-foreground">
                          <p className="font-semibold text-foreground">Builder summary</p>
                          <ul className="mt-1 space-y-1">
                            <li>
                              Semantic metrics: <span className="font-semibold">{metricDefinitions.length}</span>
                            </li>
                            <li>
                              Marts discovered: <span className="font-semibold">{biResult.marts.length}</span>
                            </li>
                          </ul>
                        </div>
                      </div>
                      <div className="space-y-6">
                        <div className="space-y-3">
                          <Label htmlFor="bi-question">Ask the BI assistant</Label>
                          <div className="flex flex-col gap-2">
                            <Textarea
                              id="bi-question"
                              placeholder="مثال: ما هو معدل الدفع عند الاستلام حسب الوجهة؟"
                              value={biLlmQuestion}
                              onChange={(e) => setBiLlmQuestion(e.target.value)}
                              rows={3}
                              className="text-sm"
                            />
                            <div className="flex items-center justify-between gap-2">
                              <Button size="sm" onClick={handleRunBiPlan} disabled={isRunningBiPlan}>
                                <Sparkles className="mr-2 h-4 w-4" />
                                {isRunningBiPlan ? "Planning..." : "Ask"}
                              </Button>
                              {!biResult.llm_enabled ? (
                                <p className="text-xs text-muted-foreground">
                                  LLM disabled – deterministic planner in use.
                                </p>
                              ) : null}
                            </div>
                          </div>
                          {biLlmResult?.plan ? (
                            <pre className="max-h-40 overflow-auto rounded-md border border-border bg-muted/20 p-3 text-xs">
                              {JSON.stringify(biLlmResult.plan, null, 2)}
                            </pre>
                          ) : null}
                        </div>
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-sm font-semibold text-foreground">
                                {biChartMeta?.title ?? "Metric preview"}
                              </p>
                              {biChartMeta?.description ? (
                                <p className="text-xs text-muted-foreground">{biChartMeta.description}</p>
                              ) : null}
                            </div>
                            <div className="flex items-center gap-2">
                              <Button size="sm" variant="outline" onClick={handleExplainChart} disabled={isExplainingChart}>
                                <Sparkles className="mr-2 h-4 w-4" />
                                {isExplainingChart ? "Explaining..." : "Explain with AI"}
                              </Button>
                              {(isRunningBiQuery || isRunningBiPlan) && (
                                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                              )}
                            </div>
                          </div>
                          <VisualizationAdapter
                            data={biChartData ?? []}
                            viz={{
                              chartType: biChartMeta?.chartType ?? "bar",
                              xKey: biChartMeta?.xKey ?? "dt",
                              valueKey: biChartMeta?.valueKey ?? "val",
                            }}
                          />
                          {biChartData ? (
                            <div className="max-h-64 overflow-auto rounded-md border border-border">
                              <table className="w-full text-xs">
                                <thead className="bg-muted/40">
                                  <tr>
                                    {Object.keys(biChartData[0] ?? {}).map((column) => (
                                      <th
                                        key={column}
                                        className="px-2 py-1 text-left font-medium text-muted-foreground"
                                      >
                                        {column}
                                      </th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {biChartData.map((row, rowIndex) => (
                                    <tr key={rowIndex} className="border-t border-border/60">
                                      {Object.keys(biChartData[0] ?? {}).map((column) => (
                                        <td key={`${rowIndex}-${column}`} className="px-2 py-1">
                                          {String(row[column] ?? "")}
                                        </td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <div className="flex h-24 items-center justify-center rounded-md border border-dashed border-border text-xs text-muted-foreground">
                              Select a metric or ask the assistant to preview data.
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ) : null}
              <Card>
                <CardHeader>
                  <CardTitle>Phase Dependencies</CardTitle>
                  <CardDescription>Understanding the pipeline flow</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 overflow-x-auto pb-2">
                      {phases.map((phase, index) => (
                        <div key={phase.id} className="flex items-center gap-2">
                          <div
                            className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg border-2 font-bold ${
                              phase.id === selectedPhase
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border bg-card text-foreground"
                            }`}
                          >
                            {phase.id}
                          </div>
                          {index < phases.length - 1 && <div className="h-0.5 w-8 flex-shrink-0 bg-border" />}
                        </div>
                      ))}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Each phase depends on outputs from previous stages. Phase 01 ingests raw data, Phase 08 generates
                      insights, Phase 09 validates against KPIs, and Phase 10 builds semantic BI assets ready for the
                      assistant and dashboards.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
