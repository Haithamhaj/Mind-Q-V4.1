"use client"

import type React from "react"
import Link from "next/link"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import * as echarts from "echarts"
import { Loader2, Download, Search, FileJson, FileSpreadsheet, FileCode, CheckCircle2 } from "lucide-react"

import { Sidebar } from "@/components/sidebar"
import { Header } from "@/components/header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  api,
  ArtifactContentResponse,
  ArtifactPhaseInfo,
  BiMetricResponse,
  PipelineRunInfo,
  RunArtifactsResponse,
  RunListResponse,
} from "@/lib/api"

interface ChartProps {
  option: echarts.EChartsOption
}

const chartBackground = "#0F172A"

function EChart({ option }: ChartProps) {
  const chartRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!chartRef.current) {
      return
    }
    const instance = echarts.init(chartRef.current)
    instance.setOption(option, true)
    const handleResize = () => instance.resize()
    window.addEventListener("resize", handleResize)
    return () => {
      window.removeEventListener("resize", handleResize)
      instance.dispose()
    }
  }, [option])

  return <div ref={chartRef} className="h-80 w-full rounded-lg border border-border bg-card" />
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B"
  const units = ["B", "KB", "MB", "GB", "TB"]
  let size = bytes
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(size >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}

function createMetricOption(
  metric: Record<string, unknown> | undefined,
  response: BiMetricResponse | null,
): echarts.EChartsOption {
  const rows = response?.data ?? []

  const metricName = metric && typeof metric["name"] === "string" ? (metric["name"] as string) : undefined
  const metricId = metric && typeof metric["id"] === "string" ? (metric["id"] as string) : undefined
  const defaultChart =
    metric && typeof metric["default_chart"] === "string" ? (metric["default_chart"] as string) : "line"
  const unitValue = metric && typeof metric["unit"] === "string" ? (metric["unit"] as string) : ""

  if (!metric || !rows.length) {
    return {
      backgroundColor: chartBackground,
      title: {
        text: metric ? String(metricName ?? metricId ?? "Metric") : "Metric",
        left: "center",
        textStyle: { color: "#E2E8F0", fontWeight: "600" },
      },
      graphic: {
        type: "text",
        left: "center",
        top: "middle",
        style: {
          text: "No data available for this metric",
          fill: "#64748B",
          fontSize: 16,
        },
      },
    }
  }

  const firstRow = rows[0] ?? {}
  const keys = Object.keys(firstRow)
  const numericKey = keys.find((key) => typeof (firstRow as Record<string, unknown>)[key] === "number") || "val"
  const categoryKey = keys.find((key) => key !== numericKey) || "category"

  const chartType = defaultChart === "bar" ? "bar" : defaultChart === "line" ? "line" : "line"

  const categories = rows.map((row) => String((row as Record<string, unknown>)[categoryKey] ?? ""))
  const values = rows.map((row) => Number((row as Record<string, unknown>)[numericKey] ?? 0))

  const titleText = String(metricName ?? metricId ?? "Metric")

  return {
    backgroundColor: chartBackground,
    title: {
      text: titleText,
      left: "center",
      textStyle: { color: "#E2E8F0", fontWeight: "600", fontSize: 16 },
    },
    tooltip: {
      trigger: chartType === "bar" ? "item" : "axis",
      backgroundColor: "#1E293B",
      borderColor: "#334155",
      valueFormatter: (value) => {
        if (typeof value !== "number") return String(value ?? "")
        const formatted = Math.abs(value) >= 1000 ? value.toLocaleString() : value.toFixed(2)
        return unitValue ? `${formatted} ${unitValue}` : formatted
      },
    },
    grid: {
      left: "5%",
      right: "4%",
      bottom: 60,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      boundaryGap: chartType === "bar",
      data: categories,
      axisLabel: {
        color: "#94A3B8",
        rotate: categories.length > 12 ? 45 : 0,
      },
      axisLine: { lineStyle: { color: "#1E293B" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: "#94A3B8" },
      splitLine: { lineStyle: { color: "#1E293B" } },
    },
    dataZoom: rows.length > 25 ? [{ type: "inside" }, { type: "slider" }] : undefined,
    series: [
      {
        name: titleText,
        type: chartType,
        smooth: chartType === "line",
        showSymbol: chartType !== "bar",
        lineStyle: { width: 3, color: "#38BDF8" },
        itemStyle: {
          color: chartType === "bar" ? "#6366F1" : "#38BDF8",
        },
        areaStyle: chartType === "line" ? { opacity: 0.12, color: "#38BDF8" } : undefined,
        data: values,
      },
    ],
  }
}

function getFileIcon(extension: string) {
  switch (extension) {
    case ".json":
    case ".jsonl":
    case ".yaml":
    case ".yml":
      return <FileJson className="h-5 w-5 text-primary" />
    case ".parquet":
    case ".csv":
      return <FileSpreadsheet className="h-5 w-5 text-secondary" />
    default:
      return <FileCode className="h-5 w-5 text-muted-foreground" />
  }
}

function serializeContent(preview: ArtifactContentResponse | null): string {
  if (!preview) {
    return ""
  }
  if (typeof preview.content === "string") {
    return preview.content
  }
  return JSON.stringify(preview.content, null, 2)
}

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function Label({ children, className, ...props }: React.ComponentPropsWithoutRef<"label">) {
  return (
    <label
      className={`text-sm font-medium leading-none text-muted-foreground ${className ?? ""}`}
      {...props}
    >
      {children}
    </label>
  )
}

export default function ResultsPage() {
  const [runs, setRuns] = useState<PipelineRunInfo[]>([])
  const [selectedRun, setSelectedRun] = useState<string>("")
  const [artifactsRoot, setArtifactsRoot] = useState<string>("")
  const [artifacts, setArtifacts] = useState<ArtifactPhaseInfo[]>([])
  const [searchQuery, setSearchQuery] = useState<string>("")
  const [artifactPreview, setArtifactPreview] = useState<ArtifactContentResponse | null>(null)
  const [selectedFilePath, setSelectedFilePath] = useState<string>("")
  const [metrics, setMetrics] = useState<Array<Record<string, unknown>>>([])
  const [selectedMetricId, setSelectedMetricId] = useState<string>("")
  const [metricResponse, setMetricResponse] = useState<BiMetricResponse | null>(null)
  // KNIME quick summary
  const [knimeSummary, setKnimeSummary] = useState<Record<string, unknown> | null>(null)
  const [knimeFeatureReport, setKnimeFeatureReport] = useState<Record<string, unknown> | null>(null)

  const [isLoadingRuns, setIsLoadingRuns] = useState<boolean>(true)
  const [runsError, setRunsError] = useState<string | null>(null)
  const [isLoadingArtifacts, setIsLoadingArtifacts] = useState<boolean>(false)
  const [artifactsError, setArtifactsError] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isMetricLoading, setIsMetricLoading] = useState<boolean>(false)
  const [metricError, setMetricError] = useState<string | null>(null)

  const refreshRuns = useCallback(() => {
    setIsLoadingRuns(true)
    setRunsError(null)
    api
      .listRuns()
      .then((response: RunListResponse) => {
        const orderedRuns = response.runs
        setRuns(orderedRuns)
        setArtifactsRoot(String(response.artifacts_root || ""))
        if (orderedRuns.length === 0) {
          setSelectedRun("")
          return
        }
        const runIds = new Set(orderedRuns.map((run) => run.run_id))
        if (!selectedRun || !runIds.has(selectedRun)) {
          setSelectedRun(orderedRuns[0].run_id)
        }
      })
      .catch((error: Error) => {
        setRuns([])
        setRunsError(error.message)
      })
      .finally(() => {
        setIsLoadingRuns(false)
      })
  }, [selectedRun])

  useEffect(() => {
    refreshRuns()
  }, [refreshRuns])

  useEffect(() => {
    if (!selectedRun) {
      setArtifacts([])
      setMetrics([])
      setSelectedMetricId("")
      setArtifactPreview(null)
      setSelectedFilePath("")
      return
    }
    let active = true
    setIsLoadingArtifacts(true)
    setArtifactsError(null)
    setArtifactPreview(null)
    setSelectedFilePath("")
    Promise.all([api.listRunArtifacts(selectedRun, artifactsRoot), api.getBiMeta(selectedRun, artifactsRoot)])
      .then(([artifactResponse, metaResponse]: [RunArtifactsResponse, Record<string, unknown>]) => {
        if (!active) return
        setArtifacts(artifactResponse.phases || [])
        const metaRecord = metaResponse as Record<string, unknown>
        const semanticPayload =
          metaRecord && typeof metaRecord["semantic"] === "object"
            ? (metaRecord["semantic"] as Record<string, unknown>)
            : undefined
        const semanticMetricsCandidate =
          semanticPayload && Array.isArray(semanticPayload["metrics"])
            ? (semanticPayload["metrics"] as Array<Record<string, unknown>>)
            : null
        const rawMetrics =
          semanticMetricsCandidate ??
          (Array.isArray(metaRecord["metrics"])
            ? (metaRecord["metrics"] as Array<Record<string, unknown>>)
            : [])
        setMetrics(rawMetrics)
        if (rawMetrics.length) {
          const metricIds = rawMetrics.map((item) => String(item.id ?? ""))
          if (!metricIds.includes(selectedMetricId)) {
            setSelectedMetricId(metricIds[0])
          }
        } else {
          setSelectedMetricId("")
        }
      })
      .catch((error: Error) => {
        if (!active) return
        setArtifactsError(error.message)
        setArtifacts([])
        setMetrics([])
        setSelectedMetricId("")
      })
      .finally(() => {
        if (active) {
          setIsLoadingArtifacts(false)
        }
      })
    return () => {
      active = false
    }
  }, [selectedRun, selectedMetricId, artifactsRoot])

  const filteredPhases = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()
    if (!query) {
      return artifacts
    }
    return artifacts
      .map((phase) => {
        const matchesPhase =
          phase.label.toLowerCase().includes(query) || phase.id.toLowerCase().includes(query)
        if (matchesPhase) {
          return phase
        }
        const files = phase.files.filter(
          (file) =>
            file.name.toLowerCase().includes(query) || file.path.toLowerCase().includes(query),
        )
        if (files.length) {
          return { ...phase, files }
        }
        return null
      })
      .filter((phase): phase is ArtifactPhaseInfo => Boolean(phase && phase.files.length))
  }, [artifacts, searchQuery])

  const selectedMetric = useMemo(
    () => metrics.find((metric) => String(metric.id ?? "") === selectedMetricId),
    [metrics, selectedMetricId],
  )

  const chartOption = useMemo(
    () => createMetricOption(selectedMetric, metricResponse),
    [selectedMetric, metricResponse],
  )

  const handleViewArtifact = async (path: string) => {
    if (!selectedRun) return
    setIsPreviewLoading(true)
    setPreviewError(null)
    setSelectedFilePath(path)
    try {
      const preview = await api.getArtifactContent(selectedRun, path, artifactsRoot)
      setArtifactPreview(preview)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to load artifact"
      setPreviewError(message)
      setArtifactPreview(null)
    } finally {
      setIsPreviewLoading(false)
    }
  }

  const handleDownloadArtifact = async (path: string) => {
    if (!selectedRun) return
    setPreviewError(null)
    try {
      const preview = await api.getArtifactContent(selectedRun, path, artifactsRoot)
      const contentText =
        typeof preview.content === "string"
          ? preview.content
          : JSON.stringify(preview.content, null, 2)
      const blob = new Blob([contentText], { type: "application/json;charset=utf-8" })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = path.split("/").pop() || "artifact.json"
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to download artifact"
      setPreviewError(message)
    }
  }

  const hasRuns = runs.length > 0
  const selectedRunInfo = runs.find((run) => run.run_id === selectedRun) ?? null
  const analysisHref = useMemo(() => {
    if (!selectedRun) {
      return "#"
    }
    const base = `/runs/${selectedRun}/analysis`
    return artifactsRoot ? `${base}?artifacts_root=${encodeURIComponent(artifactsRoot)}` : base
  }, [selectedRun, artifactsRoot])
  const metricSql =
    selectedMetric && typeof selectedMetric["sql"] === "string"
      ? (selectedMetric["sql"] as string)
      : null
  const previewContent = serializeContent(artifactPreview)
  const artifactFileCount = useMemo(
    () => artifacts.reduce((total, phase) => total + phase.files.length, 0),
    [artifacts],
  )

  useEffect(() => {
    if (!selectedRun || !selectedMetricId) {
      setMetricResponse(null)
      return
    }
    let active = true
    setIsMetricLoading(true)
    setMetricError(null)
    api
      .getBiMetric(selectedRun, selectedMetricId)
      .then((response) => {
        if (!active) return
        setMetricResponse(response)
      })
      .catch((error: Error) => {
        if (!active) return
        setMetricError(error.message)
        setMetricResponse(null)
      })
      .finally(() => {
        if (active) {
          setIsMetricLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [selectedRun, selectedMetricId])

  // Auto-load KNIME key files if present
  useEffect(() => {
    if (!selectedRun || artifacts.length === 0) {
      setKnimeSummary(null)
      setKnimeFeatureReport(null)
      return
    }
    const allFiles = artifacts.flatMap((p) => p.files || [])
    const profileFiles = allFiles.filter((f) => f.path.toLowerCase().includes("phase_07_knime/profile/"))
    const byName = (name: string) => profileFiles.find((f) => f.name === name)?.path
    const summaryPath = byName("bridge_summary.json")
    const featureReportPath = byName("feature_report.json")
    if (summaryPath) {
      api
        .getArtifactContent(selectedRun, summaryPath, artifactsRoot)
        .then((res) => setKnimeSummary((res.content as Record<string, unknown>) ?? null))
        .catch(() => setKnimeSummary(null))
    } else {
      setKnimeSummary(null)
    }
    if (featureReportPath) {
      api
        .getArtifactContent(selectedRun, featureReportPath, artifactsRoot)
        .then((res) => setKnimeFeatureReport((res.content as Record<string, unknown>) ?? null))
        .catch(() => setKnimeFeatureReport(null))
    } else {
      setKnimeFeatureReport(null)
    }
  }, [selectedRun, artifacts, artifactsRoot])

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto bg-background p-6">
          <div className="mx-auto max-w-7xl space-y-6">
            <div>
              <h1 className="text-3xl font-bold text-foreground">Results & Artifacts</h1>
              <p className="text-muted-foreground">
                Browse pipeline outputs, inspect stage artifacts, and explore BI charts powered by
                Apache ECharts.
              </p>
            </div>

            <Card>
              <CardHeader className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <CardTitle>Run Selection</CardTitle>
                  <CardDescription>
                    Choose a pipeline run and search for artifacts across all phases.
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={refreshRuns} disabled={isLoadingRuns}>
                    {isLoadingRuns ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Refreshing
                      </>
                    ) : (
                      "Refresh"
                    )}
                  </Button>
                  <Button asChild variant="outline" size="sm" disabled={!selectedRun}>
                    <Link href={analysisHref} aria-disabled={!selectedRun}>
                      Run Analysis
                    </Link>
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-[2fr,1fr]">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="run-select">Select Run</Label>
                    <select
                      id="run-select"
                      value={selectedRun}
                      onChange={(event) => setSelectedRun(event.target.value)}
                      className="w-full rounded-md border border-border bg-muted/20 px-3 py-2 text-sm text-foreground outline-none focus-visible:border-primary"
                      disabled={!hasRuns || isLoadingRuns}
                    >
                      {!hasRuns && <option value="">No runs available</option>}
                      {runs.map((run) => (
                        <option key={run.run_id} value={run.run_id}>
                          {run.run_id}
                        </option>
                      ))}
                    </select>
                    {selectedRunInfo && (
                      <p className="text-xs text-muted-foreground">
                        Last updated: {formatDateTime(selectedRunInfo.updated_at)}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="artifact-search">Search Artifacts</Label>
                    <div className="relative flex items-center">
                      <Search className="absolute left-3 h-4 w-4 text-muted-foreground" />
                      <Input
                        id="artifact-search"
                        value={searchQuery}
                        onChange={(event) => setSearchQuery(event.target.value)}
                        placeholder="Search by phase or file name..."
                        className="pl-9"
                        disabled={!hasRuns}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {artifactFileCount} file{artifactFileCount === 1 ? "" : "s"} across {artifacts.length} phase{artifacts.length === 1 ? "" : "s"}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {runsError && (
              <Card className="border-destructive/40 bg-destructive/10">
                <CardContent className="py-4 text-destructive-foreground">
                  Failed to load pipeline runs: {runsError}
                </CardContent>
              </Card>
            )}

            <div className="grid gap-6 xl:grid-cols-[2fr,1fr]">
              <Card>
                <CardHeader>
                  <CardTitle>Pipeline Artifacts</CardTitle>
                  <CardDescription>
                    Actual outputs fetched from the backend artifacts directory.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {isLoadingArtifacts ? (
                    <div className="flex items-center justify-center py-12 text-muted-foreground">
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      Loading artifacts…
                    </div>
                  ) : artifactsError ? (
                    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive-foreground">
                      {artifactsError}
                    </div>
                  ) : filteredPhases.length === 0 ? (
                    <div className="rounded-md border border-dashed border-border/60 p-6 text-center text-sm text-muted-foreground">
                      {hasRuns
                        ? "No artifacts match the current search."
                        : "Select a run to view its artifacts."}
                    </div>
                  ) : (
                    filteredPhases.map((phase) => (
                      <div key={phase.id} className="space-y-3 rounded-lg border border-border/60 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">{phase.label}</Badge>
                            <span className="text-xs text-muted-foreground">{phase.id}</span>
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {phase.files.length} file{phase.files.length === 1 ? "" : "s"}
                          </span>
                        </div>
                        <div className="space-y-2">
                          {phase.files.map((file) => {
                            const extension = file.name.split(".").pop()?.toLowerCase() ?? ""
                            return (
                              <div
                                key={file.path}
                                className="flex items-center justify-between gap-3 rounded-md border border-border/40 bg-muted/10 px-3 py-2"
                              >
                                <div className="flex items-center gap-3">
                                  {getFileIcon(extension)}
                                  <div>
                                    <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                                      {file.name}
                                      <CheckCircle2 className="h-4 w-4 text-secondary" />
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                      {formatBytes(file.size)} | {formatDateTime(file.updated_at)}
                                    </p>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleViewArtifact(file.path)}
                                    disabled={isPreviewLoading}
                                  >
                                    View
                                  </Button>
                                  <Button variant="outline" size="sm" onClick={() => handleDownloadArtifact(file.path)}>
                                    <Download className="h-4 w-4" />
                                  </Button>
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Stage 10 BI Metrics</CardTitle>
                    <CardDescription>
                      Interactive charts rendered with Apache ECharts using semantic layer SQL.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="metric-select">Select Metric</Label>
                      <select
                        id="metric-select"
                        value={selectedMetricId}
                        onChange={(event) => setSelectedMetricId(event.target.value)}
                        className="rounded-md border border-border bg-muted/20 px-3 py-2 text-sm text-foreground outline-none focus-visible:border-primary"
                        disabled={metrics.length === 0}
                      >
                        {metrics.length === 0 && <option value="">No metrics available</option>}
                        {metrics.map((metric) => {
                          const metricId = String(metric.id ?? "")
                          return (
                            <option key={metricId} value={metricId}>
                              {String(metric.name ?? metricId)}
                            </option>
                          )
                        })}
                      </select>
                    </div>
                    {metricError && (
                      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive-foreground">
                        {metricError}
                      </div>
                    )}
                    {isMetricLoading ? (
                      <div className="flex items-center justify-center py-16 text-muted-foreground">
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                        Loading chart…
                      </div>
                    ) : (
                      <EChart option={chartOption} />
                    )}
                    {metricSql && (
                      <div className="rounded-md border border-border/40 bg-muted/10 p-3">
                        <Label className="text-xs uppercase text-muted-foreground">SQL</Label>
                        <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground">
                          {metricSql}
                        </pre>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>KNIME Results (Stage 07)</CardTitle>
                    <CardDescription>
                      Quick access to KNIME Bridge outputs under <code>phase_07_knime/profile/</code>.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {knimeSummary ? (
                      <div className="rounded-md border border-border/60 bg-muted/10 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline">Exit: {String((knimeSummary as any)?.batch?.exit_code ?? "N/A")}</Badge>
                          {Boolean((knimeSummary as any)?.batch?.duration_s) && (
                            <Badge variant="secondary">{String((knimeSummary as any)?.batch?.duration_s)}s</Badge>
                          )}
                          <Badge variant="outline">Mode: {String((knimeSummary as any)?.mode ?? "-")}</Badge>
                        </div>
                        {Boolean((knimeSummary as any)?.batch?.stdout_path) && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            Log: {(knimeSummary as any)?.batch?.stdout_path}
                          </p>
                        )}
                      </div>
                    ) : (
                      <div className="rounded-md border border-dashed border-border/60 p-3 text-xs text-muted-foreground">
                        bridge_summary.json not found yet.
                      </div>
                    )}

                    {knimeFeatureReport ? (
                      <div className="rounded-md border border-border/60 bg-muted/10 p-3">
                        <div className="mb-1 text-sm font-medium text-foreground">Feature Report (excerpt)</div>
                        <pre className="max-h-48 overflow-auto text-xs text-muted-foreground">
                          {JSON.stringify(knimeFeatureReport, null, 2)}
                        </pre>
                      </div>
                    ) : null}
                    {(() => {
                      const profileFiles = artifacts
                        .flatMap((p) => p.files)
                        .filter((f) => f.path.toLowerCase().includes("phase_07_knime/profile/"))
                      if (!selectedRun) {
                        return (
                          <div className="text-sm text-muted-foreground">Select a run to view KNIME outputs.</div>
                        )
                      }
                      if (!profileFiles.length) {
                        return (
                          <div className="rounded-md border border-dashed border-border/60 p-3 text-sm text-muted-foreground">
                            No KNIME profile outputs detected yet. Ensure phase 07 ran with KNIME and try again.
                          </div>
                        )
                      }
                      const important = [
                        "feature_report.json",
                        "bridge_summary.json",
                        "model_metrics.json",
                        "feature_importance.json",
                        "predictions.parquet",
                      ]
                      const byName = (name: string) => profileFiles.find((f) => f.name === name)
                      const items = important
                        .map((name) => byName(name))
                        .filter((x): x is NonNullable<typeof x> => Boolean(x))
                      return (
                        <div className="space-y-2">
                          {items.map((file) => (
                            <div
                              key={file.path}
                              className="flex items-center justify-between gap-3 rounded-md border border-border/40 bg-muted/10 px-3 py-2"
                            >
                              <div className="flex items-center gap-3">
                                {getFileIcon(("." + (file.name.split(".").pop() ?? "")).toLowerCase())}
                                <div>
                                  <p className="text-sm font-medium text-foreground">{file.name}</p>
                                  <p className="text-xs text-muted-foreground">
                                    {formatBytes(file.size)} | {formatDateTime(file.updated_at)}
                                  </p>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleViewArtifact(file.path)}
                                  disabled={isPreviewLoading || file.name.endsWith(".parquet")}
                                  title={file.name.endsWith(".parquet") ? "Preview not supported; use Download" : "View"}
                                >
                                  View
                                </Button>
                                <Button variant="outline" size="sm" onClick={() => handleDownloadArtifact(file.path)}>
                                  <Download className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          ))}
                          <div className="pt-1 text-xs text-muted-foreground">
                            JSON files support inline preview below. Parquet needs download to inspect.
                          </div>
                        </div>
                      )
                    })()}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Artifact Viewer</CardTitle>
                    <CardDescription>
                      Inline preview for JSON, JSONL, CSV, YAML, and text artifacts.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {selectedFilePath ? (
                      <div className="text-xs text-muted-foreground">
                        Viewing: <span className="font-mono text-foreground">{selectedFilePath}</span>
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground">Select a file to preview its contents.</p>
                    )}
                    {previewError && (
                      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive-foreground">
                        {previewError}
                      </div>
                    )}
                    <div className="rounded-lg border border-border/60 bg-muted/10 p-4">
                      {isPreviewLoading ? (
                        <div className="flex items-center justify-center py-10 text-muted-foreground">
                          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                          Loading artifact content…
                        </div>
                      ) : previewContent ? (
                        <pre className="max-h-96 overflow-auto text-xs leading-relaxed text-muted-foreground">
                          {previewContent}
                        </pre>
                      ) : (
                        <div className="py-8 text-center text-sm text-muted-foreground">No artifact selected.</div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
