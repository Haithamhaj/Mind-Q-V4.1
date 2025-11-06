"use client"

import type React from "react"

import { useState, useRef, useMemo, useEffect, useCallback } from "react"
import type { PipelinePhaseStatus, PipelineProgress, PipelineResponse } from "@/lib/api"
import { Sidebar } from "@/components/sidebar"
import { Header } from "@/components/header"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { HelpTrigger } from "@/components/help/help-trigger"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Progress } from "@/components/ui/progress"
import { AlertTriangle, Play, Plus, X } from "lucide-react"
import { api } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"
import { useLanguage } from "@/context/language-context"

const generateRunId = () => `run-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`

type ParsedPipelineError = {
  headline: string
  reason: string | null
  references: string[]
}

const parsePipelineErrorMessage = (message: string): ParsedPipelineError => {
  const [main, filesPart] = message.split(" Related files:")
  const trimmedMain = main.trim()
  const colonIndex = trimmedMain.indexOf(":")
  const headline = colonIndex >= 0 ? trimmedMain.slice(0, colonIndex).trim() : trimmedMain
  const reason = colonIndex >= 0 ? trimmedMain.slice(colonIndex + 1).trim() : null
  const references = filesPart
    ? filesPart
        .split(",")
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0)
    : []
  return { headline, reason, references }
}

export default function PipelinePage() {
  const initialRunId = useMemo(() => generateRunId(), [])
  const { translate } = useLanguage()
  const [runId, setRunId] = useState(initialRunId)
  const [dataFiles, setDataFiles] = useState<string[]>([])
  const [slaFiles, setSlaFiles] = useState<string[]>([])
  const [stopOnError, setStopOnError] = useState(true)
  const [llmSummary, setLlmSummary] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [pipelineResult, setPipelineResult] = useState<PipelineResponse | null>(null)
  const [pipelineError, setPipelineError] = useState<string | null>(null)
  const [pipelineProgress, setPipelineProgress] = useState<PipelineProgress | null>(null)
  const [isUploadingDataFiles, setIsUploadingDataFiles] = useState(false)
  const [isUploadingSlaFiles, setIsUploadingSlaFiles] = useState(false)
  const { toast } = useToast()

  // LLM Advisor state
  const [advisorLoading, setAdvisorLoading] = useState(false)
  const [advisorSummary, setAdvisorSummary] = useState<string>("")
  const [advisorRecommendedConfig, setAdvisorRecommendedConfig] = useState<Record<string, unknown> | null>(null)
  const [advisorAutoDecide, setAdvisorAutoDecide] = useState<boolean>(false)
  // Editable advisor fields
  const [advTargetColumn, setAdvTargetColumn] = useState<string>("")
  const [advClusteringK, setAdvClusteringK] = useState<string>("")
  const [advAssocSupport, setAdvAssocSupport] = useState<string>("")
  const [advAssocConfidence, setAdvAssocConfidence] = useState<string>("")
  const [advRecTopK, setAdvRecTopK] = useState<string>("")

  const phaseStatusLabels = useMemo<Record<PipelinePhaseStatus, string>>(
    () => ({
      pending: translate("Pending"),
      running: translate("Running"),
      completed: translate("Completed"),
      skipped: translate("Skipped"),
      deferred: translate("Deferred"),
    }),
    [translate],
  )

  const pipelineStageSummaries = useMemo(
    () => [
      { stage: "01", name: translate("Ingestion"), desc: translate("Data and SLA ingestion") },
      { stage: "02", name: translate("Quality"), desc: translate("Data quality checks") },
      { stage: "03", name: translate("Schema"), desc: translate("Schema extraction") },
      { stage: "03.5", name: translate("TextOps"), desc: translate("Text normalization and NLP") },
      { stage: "04", name: translate("Profile"), desc: translate("Data profiling") },
      { stage: "05", name: translate("Missing"), desc: translate("Imputation") },
      { stage: "06", name: translate("Standardize"), desc: translate("Feature engineering") },
      { stage: "07", name: translate("Readiness"), desc: translate("Readiness analysis") },
      { stage: "08", name: translate("Insights"), desc: translate("Operational insights") },
      { stage: "09", name: translate("Validation"), desc: translate("Business validation") },
      { stage: "10", name: translate("BI delivery"), desc: translate("Semantic marts and dashboards") },
    ],
    [translate],
  )

  const parsedPipelineError = pipelineError ? parsePipelineErrorMessage(pipelineError) : null

  const dataFileInputRef = useRef<HTMLInputElement>(null)
  const slaFileInputRef = useRef<HTMLInputElement>(null)
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pollingRunIdRef = useRef<string | null>(null)
  const isMountedRef = useRef(true)

  const stopPolling = useCallback(() => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }
    pollingRunIdRef.current = null
  }, [])

  const pollPipelineCompletion = useCallback(
    (targetRunId: string) => {
      stopPolling()
      pollingRunIdRef.current = targetRunId
      const maxAttempts = 240
      const intervalMs = 5000
      let attempts = 0

      const poll = async () => {
        if (!isMountedRef.current || pollingRunIdRef.current !== targetRunId) {
          return
        }
        attempts += 1
        try {
          const status = await api.getPipelineStatus(targetRunId)
          if (!isMountedRef.current || pollingRunIdRef.current !== targetRunId) {
            return
          }
          setPipelineProgress(status)

          if (status.status === "failed") {
            stopPolling()
            setIsRunning(false)
            const message =
              status.error ?? translate("Pipeline {runId} failed.", { runId: targetRunId })
            setPipelineError(message)
            toast({
              title: translate("Pipeline failed"),
              description: message,
              variant: "destructive",
            })
            return
          }

          if (status.status === "completed") {
            stopPolling()
            try {
              const artifacts = await api.listRunArtifacts(targetRunId)
              if (isMountedRef.current) {
                const phases = artifacts.phases ?? []
                setPipelineError(null)
                setPipelineResult({
                  run_id: artifacts.run_id,
                  phases: phases.map((phase) => ({
                    phase: phase.id,
                    label: phase.label,
                    files: phase.files,
                  })) as Array<Record<string, unknown>>,
                })
              }
            } catch (artifactError) {
              console.error("[v0] Fetching run artifacts failed:", artifactError)
            }
            setIsRunning(false)
            toast({
              title: translate("Pipeline completed"),
              description: translate("Pipeline {runId} finished successfully.", { runId: targetRunId }),
            })
            return
          }
        } catch (error) {
          console.error("[v0] Polling pipeline status failed:", error)
        }

        if (attempts >= maxAttempts) {
          stopPolling()
          if (!isMountedRef.current) {
            return
          }
          setIsRunning(false)
          setPipelineError(translate("Pipeline is still running or failed. Please review artifacts for details."))
          toast({
            title: translate("Pipeline status timed out"),
            description: translate("Unable to confirm completion for {runId}. Check the pipeline artifacts.", {
              runId: targetRunId,
            }),
            variant: "destructive",
          })
          return
        }

        pollTimeoutRef.current = setTimeout(poll, intervalMs)
      }

      pollTimeoutRef.current = setTimeout(poll, 0)
    },
    [stopPolling, toast, translate],
  )

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      stopPolling()
    }
  }, [stopPolling])

  const progressPercent = pipelineProgress ? Math.round((pipelineProgress.percent_complete ?? 0) * 100) : 0
  const currentPhaseLabel =
    pipelineProgress && pipelineProgress.current_phase
      ? pipelineProgress.phases.find((phase) => phase.id === pipelineProgress.current_phase)?.label ??
        pipelineProgress.current_phase
      : null

  const addDataFile = () => {
    dataFileInputRef.current?.click()
  }

  const addManualDataFile = () => {
    setDataFiles((prev) => [...prev, ""])
  }

  const handleDataFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) {
      return
    }

    const selectedFiles = Array.from(files)
    setIsUploadingDataFiles(true)

    try {
      const uploads = await Promise.all(selectedFiles.map((file) => api.uploadFile(file)))
      setDataFiles((prev) => {
        const existing = [...prev]
        const newPaths = uploads.map((upload) => upload.path)
        return [...existing, ...newPaths]
      })
      const count = uploads.length
      toast({
        title: translate("Data ready"),
        description:
          count === 1
            ? translate("Uploaded 1 data file for processing.")
            : translate("Uploaded {count} data files for processing.", { count }),
      })
    } catch (error) {
      console.error("[v0] Data file upload failed:", error)
      toast({
        title: translate("Upload failed"),
        description: error instanceof Error ? error.message : translate("Failed to upload data files"),
        variant: "destructive",
      })
    } finally {
      setIsUploadingDataFiles(false)
      if (dataFileInputRef.current) {
        dataFileInputRef.current.value = ""
      }
    }
  }

  const removeDataFile = (index: number) => setDataFiles((prev) => prev.filter((_, i) => i !== index))
  const updateDataFile = (index: number, value: string) => {
    setDataFiles((prev) => {
      const newFiles = [...prev]
      newFiles[index] = value
      return newFiles
    })
  }

  const addSlaFile = () => {
    slaFileInputRef.current?.click()
  }

  const addManualSlaFile = () => {
    setSlaFiles((prev) => [...prev, ""])
  }

  const handleSlaFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) {
      return
    }

    const selectedFiles = Array.from(files)
    setIsUploadingSlaFiles(true)

    try {
      const uploads = await Promise.all(selectedFiles.map((file) => api.uploadFile(file)))
      setSlaFiles((prev) => {
        const existing = [...prev]
        const newPaths = uploads.map((upload) => upload.path)
        return [...existing, ...newPaths]
      })
      const count = uploads.length
      toast({
        title: translate("SLA files ready"),
        description:
          count === 1
            ? translate("Uploaded 1 SLA document.")
            : translate("Uploaded {count} SLA documents.", { count }),
      })
    } catch (error) {
      console.error("[v0] SLA file upload failed:", error)
      toast({
        title: translate("Upload failed"),
        description: error instanceof Error ? error.message : translate("Failed to upload SLA files"),
        variant: "destructive",
      })
    } finally {
      setIsUploadingSlaFiles(false)
      if (slaFileInputRef.current) {
        slaFileInputRef.current.value = ""
      }
    }
  }

  const removeSlaFile = (index: number) => setSlaFiles((prev) => prev.filter((_, i) => i !== index))
  const updateSlaFile = (index: number, value: string) => {
    setSlaFiles((prev) => {
      const newFiles = [...prev]
      newFiles[index] = value
      return newFiles
    })
  }

  const handleRunKnimeBridge = async (runId: string) => {
    try {
      toast({
        title: translate("KNIME Bridge"),
        description: translate("Starting KNIME Bridge for {runId}...", { runId }),
      })

      const mergedConfig: Record<string, unknown> = { run_batch: true }
      // include edited advisor fields if present
      if (advTargetColumn.trim()) mergedConfig["target_column"] = advTargetColumn.trim()
      const kNum = Number(advClusteringK)
      if (!Number.isNaN(kNum) && advClusteringK.trim()) mergedConfig["clustering_k"] = kNum
      const supNum = Number(advAssocSupport)
      if (!Number.isNaN(supNum) && advAssocSupport.trim()) mergedConfig["assoc_min_support"] = supNum
      const confNum = Number(advAssocConfidence)
      if (!Number.isNaN(confNum) && advAssocConfidence.trim()) mergedConfig["assoc_min_confidence"] = confNum
      const topKNum = Number(advRecTopK)
      if (!Number.isNaN(topKNum) && advRecTopK.trim()) mergedConfig["rec_top_k"] = topKNum
      if (advisorAutoDecide) {
        mergedConfig["auto_execute"] = true
      }
      if (advisorRecommendedConfig && Object.keys(advisorRecommendedConfig).length > 0) {
        Object.assign(mergedConfig, advisorRecommendedConfig)
      }
      await api.runKnimeBridge(runId, { use_defaults: true, config: mergedConfig })

      toast({
        title: translate("KNIME Bridge completed"),
        description: translate("KNIME artifacts generated successfully."),
      })

      // Refresh pipeline status
      const updatedStatus = await api.getPipelineStatus(runId)
      setPipelineProgress(updatedStatus)
    } catch (error) {
      console.error("[v0] KNIME Bridge execution failed:", error)
      toast({
        title: translate("KNIME Bridge failed"),
        description: error instanceof Error ? error.message : translate("Failed to execute KNIME Bridge"),
        variant: "destructive",
      })
    }
  }

  const handleRunPipeline = async () => {
    console.log("[v0] handleRunPipeline called")
    console.log("[v0] Current state - runId:", runId, "dataFiles:", dataFiles, "slaFiles:", slaFiles)

    const trimmedRunId = runId.trim() || generateRunId()
    if (!runId.trim()) {
      setRunId(trimmedRunId)
    }

    if (dataFiles.filter((f) => f.trim()).length === 0) {
      console.log("[v0] Validation failed - missing dataFiles")
      toast({
        title: translate("Validation error"),
        description: translate("Please upload or enter at least one data file path."),
        variant: "destructive",
      })
      return
    }

    stopPolling()
    setIsRunning(true)
    setPipelineResult(null)
    setPipelineError(null)
    setPipelineProgress(null)
    console.log("[v0] Starting pipeline execution...")

    let acceptedAsync = false

    try {
      const result = await api.runFullPipeline(
        trimmedRunId,
        {
          data_files: dataFiles.filter((f) => f.trim()),
          sla_files: slaFiles.filter((f) => f.trim()),
          stop_on_error: stopOnError,
          llm_summary: llmSummary,
        },
        { asyncMode: true },
      )

      if (result === null) {
        acceptedAsync = true
        toast({
          title: translate("Pipeline accepted"),
          description: translate("Pipeline {runId} is running in the background.", { runId: trimmedRunId }),
        })
        try {
          const statusSnapshot = await api.getPipelineStatus(trimmedRunId)
          setPipelineProgress(statusSnapshot)
        } catch (statusError) {
          console.debug("[v0] Initial status fetch failed (expected if run just started):", statusError)
        }
        pollPipelineCompletion(trimmedRunId)
      } else {
        console.log("[v0] Pipeline execution successful:", result)
        setPipelineResult(result)
        setPipelineError(null)
        try {
          const statusSnapshot = await api.getPipelineStatus(result.run_id)
          setPipelineProgress(statusSnapshot)
        } catch (statusError) {
          console.debug("[v0] Unable to read pipeline status after completion:", statusError)
        }
        toast({
          title: translate("Pipeline completed"),
          description: translate("Pipeline {runId} finished successfully.", { runId: result.run_id }),
        })
      }
    } catch (error) {
      console.error("[v0] Pipeline execution failed:", error)
      stopPolling()
      setPipelineResult(null)
      setPipelineError(error instanceof Error ? error.message : translate("Unknown error occurred"))
      setPipelineProgress(null)
      toast({
        title: translate("Pipeline failed"),
        description: error instanceof Error ? error.message : translate("Unknown error occurred"),
        variant: "destructive",
      })
    } finally {
      if (!acceptedAsync) {
        setIsRunning(false)
      }
      console.log("[v0] Pipeline execution completed")
    }
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto bg-background p-6">
          <div className="mx-auto max-w-4xl space-y-6">
            <input
              ref={dataFileInputRef}
              type="file"
              accept=".csv,.parquet"
              multiple
              className="hidden"
              onChange={handleDataFileSelect}
            />
            <input
              ref={slaFileInputRef}
              type="file"
              accept=".pdf,.docx,.csv,.html,.xlsx,.xls"
              multiple
              className="hidden"
              onChange={handleSlaFileSelect}
            />

            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-3xl font-bold text-foreground">{translate("Full pipeline execution")}</h1>
                <HelpTrigger
                  topicId="pipeline.overview"
                  aria-label={translate("Explain the pipeline workflow")}
                  variant="link"
                  buildTopic={() => ({
                    title: translate("Full pipeline automation overview"),
                    summary: translate(
                      "Runs the Mind-Q orchestration covering ingestion, data quality, schema checks, and BI delivery.",
                    ),
                    detailItems: [
                      translate("Includes data ingestion, SLA validation, enrichment, and semantic model export."),
                      translate("Supports optional SLA documents and AI-generated executive summaries."),
                      translate("Each phase reports artifacts that feed the results and BI workspaces."),
                    ],
                    suggestedQuestions: [
                      translate("Which phases are executed when I enable stop-on-error?"),
                      translate("How can I inspect artifacts after the run finishes?"),
                    ],
                  })}
                >
                  {translate("Explain")}
                </HelpTrigger>
              </div>
              <p className="text-muted-foreground">{translate("Configure and run the complete Mind-Q pipeline.")}</p>
            </div>

            {pipelineProgress && (
              <Card>
                <CardHeader>
                  <CardTitle>{translate("Pipeline progress")}</CardTitle>
                  <CardDescription>
                    {pipelineProgress.status === "completed"
                      ? translate("Run {runId} completed successfully.", { runId })
                      : pipelineProgress.status === "completed_with_deferred"
                        ? translate("Run {runId} completed with deferred tasks.", { runId })
                        : pipelineProgress.status === "failed"
                          ? translate("Run {runId} encountered an error.", { runId })
                          : translate("Tracking run {runId}.", { runId })}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-medium">
                      {pipelineProgress.status === "completed"
                        ? translate("Completed")
                        : pipelineProgress.status === "failed"
                          ? translate("Failed")
                          : currentPhaseLabel
                              ? translate("Running: {label}", { label: currentPhaseLabel })
                              : translate("Running")}
                    </div>
                    <div className="text-sm text-muted-foreground">{progressPercent}%</div>
                  </div>
                  <Progress value={progressPercent} aria-label={translate("Pipeline progress")} />
                  <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
                    {pipelineProgress.phases.map((phase) => {
                      const isAsyncJob = pipelineProgress.async_jobs && pipelineProgress.async_jobs[phase.id]
                      const asyncStatus = isAsyncJob ? pipelineProgress.async_jobs[phase.id].status : null
                      const statusLabel = phaseStatusLabels[phase.status]
                      const statusClasses =
                        phase.status === "completed"
                          ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-600"
                          : phase.status === "running"
                            ? isAsyncJob && asyncStatus === "running"
                              ? "border-blue-500/60 bg-blue-500/10 text-blue-600 animate-pulse"
                              : "border-primary/60 bg-primary/10 text-primary"
                            : phase.status === "skipped"
                              ? "border-border bg-muted/40 text-muted-foreground"
                              : phase.status === "deferred"
                                ? "border-amber-500/60 bg-amber-500/10 text-amber-600"
                                : "border-border text-muted-foreground"
                      return (
                        <div
                          key={phase.id}
                          className={`rounded-md border px-3 py-2 text-xs transition-colors ${statusClasses}`}
                        >
                          <div className="flex items-center justify-between text-[0.7rem] uppercase tracking-wide">
                            <span className="font-semibold">
                              #{phase.index.toString().padStart(2, "0")}
                            </span>
                            <span>{isAsyncJob && asyncStatus === "running" ? "⚡ " + statusLabel : statusLabel}</span>
                          </div>
                          <div className="mt-1 text-sm font-medium">{phase.label}</div>
                        </div>
                      )
                    })}
                  </div>
                  {pipelineProgress.error && (
                    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                      {pipelineProgress.error}
                    </div>
                  )}

                  {/* Async Jobs Section */}
                  {pipelineProgress.async_jobs && Object.keys(pipelineProgress.async_jobs).length > 0 && (
                    <div className="space-y-3 rounded-lg border border-primary/30 bg-primary/5 p-4">
                      <h3 className="font-semibold text-foreground">{translate("Deferred Tasks")}</h3>
                      {Object.entries(pipelineProgress.async_jobs).map(([jobId, job]) => (
                        <div key={jobId} className="space-y-2 rounded-md border border-border bg-card p-3">
                          <div className="flex items-start justify-between">
                            <div className="space-y-1">
                              <p className="font-medium text-foreground">
                                {pipelineProgress.phases.find((p) => p.id === job.phase)?.label || job.phase}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {translate("Status")}: {job.status} | {translate("Mode")}: {job.mode}
                              </p>
                            </div>
                            {job.status === "waiting_for_user" && (
                              <Button
                                size="sm"
                                onClick={() => handleRunKnimeBridge(pipelineProgress.run_id || runId)}
                                className="bg-primary hover:bg-primary/90"
                              >
                                {translate("Run KNIME")}
                              </Button>
                            )}
                          </div>
                          {job.instructions && job.instructions.length > 0 && (
                            <div className="space-y-1 text-xs text-muted-foreground">
                              {job.instructions.map((instruction, idx) => (
                                <p key={idx}>• {instruction}</p>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle>{translate("Pipeline configuration")}</CardTitle>
                <CardDescription>{translate("Set up your pipeline run parameters.")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* LLM Advisor */}
                <div className="space-y-3 rounded-lg border border-primary/30 bg-primary/5 p-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label className="text-primary">{translate("Pre-train Advisor (LLM)")}</Label>
                      <p className="text-xs text-muted-foreground">
                        {translate("Get AI-suggested configuration based on your data (e.g., target, clustering_k, thresholds).")}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={advisorLoading}
                      onClick={async () => {
                        try {
                          setAdvisorLoading(true)
                          const res = await api.runLLMSummary(runId, { use_defaults: true })
                          // Expect fields like summary, recommended_actions, and optional config in response
                          const summaryText =
                            typeof (res as any)?.summary === "string"
                              ? ((res as any).summary as string)
                              : JSON.stringify(res)
                          setAdvisorSummary(summaryText)
                          // Heuristic: if response contains a "recommended_config" object, capture it
                          const rc = (res as any)?.recommended_config
                          if (rc && typeof rc === "object") {
                            setAdvisorRecommendedConfig(rc as Record<string, unknown>)
                        // hydrate editable fields
                        setAdvTargetColumn(typeof rc.target_column === "string" ? rc.target_column : "")
                        setAdvClusteringK(
                          typeof rc.clustering_k === "number" || typeof rc.clustering_k === "string"
                            ? String(rc.clustering_k)
                            : "",
                        )
                        setAdvAssocSupport(
                          typeof rc.assoc_min_support === "number" || typeof rc.assoc_min_support === "string"
                            ? String(rc.assoc_min_support)
                            : "",
                        )
                        setAdvAssocConfidence(
                          typeof rc.assoc_min_confidence === "number" || typeof rc.assoc_min_confidence === "string"
                            ? String(rc.assoc_min_confidence)
                            : "",
                        )
                        setAdvRecTopK(
                          typeof rc.rec_top_k === "number" || typeof rc.rec_top_k === "string"
                            ? String(rc.rec_top_k)
                            : "",
                        )
                          } else {
                            setAdvisorRecommendedConfig(null)
                        setAdvTargetColumn("")
                        setAdvClusteringK("")
                        setAdvAssocSupport("")
                        setAdvAssocConfidence("")
                        setAdvRecTopK("")
                          }
                          toast({
                            title: translate("Advisor ready"),
                            description: translate("LLM summary generated. Review and continue."),
                          })
                        } catch (e) {
                          toast({
                            title: translate("Advisor failed"),
                            description: e instanceof Error ? e.message : translate("Unable to run LLM advisor"),
                            variant: "destructive",
                          })
                        } finally {
                          setAdvisorLoading(false)
                        }
                      }}
                    >
                      {advisorLoading ? translate("Running…") : translate("Run Advisor")}
                    </Button>
                  </div>
                  {advisorSummary && (
                    <div className="rounded-md border border-border/40 bg-muted/10 p-3 text-sm text-muted-foreground">
                      <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words">{advisorSummary}</pre>
                    </div>
                  )}
                  {/* Editable Advisor Config */}
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="advTargetColumn">{translate("Target column (optional)")}</Label>
                      <Input
                        id="advTargetColumn"
                        placeholder={translate("e.g., delivered_on_time")}
                        value={advTargetColumn}
                        onChange={(e) => setAdvTargetColumn(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="advClusteringK">{translate("Clustering: k")}</Label>
                      <Input
                        id="advClusteringK"
                        placeholder="5"
                        value={advClusteringK}
                        onChange={(e) => setAdvClusteringK(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="advAssocSupport">{translate("Association min support")}</Label>
                      <Input
                        id="advAssocSupport"
                        placeholder="0.02"
                        value={advAssocSupport}
                        onChange={(e) => setAdvAssocSupport(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="advAssocConfidence">{translate("Association min confidence")}</Label>
                      <Input
                        id="advAssocConfidence"
                        placeholder="0.3"
                        value={advAssocConfidence}
                        onChange={(e) => setAdvAssocConfidence(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="advRecTopK">{translate("Recommendations: top K")}</Label>
                      <Input
                        id="advRecTopK"
                        placeholder="10"
                        value={advRecTopK}
                        onChange={(e) => setAdvRecTopK(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="advisorAutoDecide">{translate("Let AI auto-decide and continue")}</Label>
                      <p className="text-xs text-muted-foreground">
                        {translate("If enabled, KNIME will run with AI-suggested defaults when available.")}
                      </p>
                    </div>
                    <Switch id="advisorAutoDecide" checked={advisorAutoDecide} onCheckedChange={setAdvisorAutoDecide} />
                  </div>
                </div>
                {/* Run ID */}
                <div className="space-y-2">
                  <Label htmlFor="runId">{translate("Run ID")}</Label>
                  <div className="flex gap-2">
                    <Input
                      id="runId"
                      placeholder={translate("Run identifier")}
                      value={runId}
                      onChange={(e) => setRunId(e.target.value)}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        const newId = generateRunId()
                        setRunId(newId)
                        toast({
                          title: translate("Run ID updated"),
                          description: translate("Generated {runId}", { runId: newId }),
                        })
                      }}
                    >
                      {translate("Regenerate")}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {translate("Unique identifier for this pipeline run.")}
                  </p>
                </div>

                {/* Data Files */}
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="space-y-0.5">
                      <Label>{translate("Data files")}</Label>
                      <p className="text-xs text-muted-foreground">
                        {translate("Upload raw datasets or enter server-accessible paths.")}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={addDataFile} disabled={isUploadingDataFiles}>
                        <Plus className="mr-2 h-4 w-4" />
                        {translate("Upload files")}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={addManualDataFile}>
                        {translate("Add path")}
                      </Button>
                    </div>
                  </div>
                  {isUploadingDataFiles ? (
                    <p className="text-xs text-muted-foreground">{translate("Uploading data files...")}</p>
                  ) : null}
                  {dataFiles.length > 0 ? (
                    <div className="space-y-2">
                      {dataFiles.map((file, index) => (
                        <div key={`${file}-${index}`} className="flex gap-2">
                          <Input
                            placeholder="/absolute/path/to/data.csv"
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
                    <p className="text-xs italic text-muted-foreground">{translate("No data files selected yet.")}</p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {translate("Uploaded files are stored under")}
                    <code className="mx-1">uploads/</code>
                    {translate(
                      "and their absolute paths are sent to the pipeline. Adjust paths if the backend expects a different location.",
                    )}
                  </p>
                </div>

                {/* SLA Files */}
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="space-y-0.5">
                      <Label>{translate("SLA files (optional)")}</Label>
                      <p className="text-xs text-muted-foreground">
                        {translate("Attach SLA documents or reference existing paths.")}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={addSlaFile} disabled={isUploadingSlaFiles}>
                        <Plus className="mr-2 h-4 w-4" />
                        {translate("Upload SLA")}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={addManualSlaFile}>
                        {translate("Add path")}
                      </Button>
                    </div>
                  </div>
                  {isUploadingSlaFiles ? (
                    <p className="text-xs text-muted-foreground">{translate("Uploading SLA documents...")}</p>
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
                    <p className="text-xs italic text-muted-foreground">{translate("No SLA documents attached.")}</p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {translate("Supported formats: PDF, DOCX, CSV, HTML, Excel. Uploaded files are stored under")}
                    <code className="mx-1">uploads/</code>
                    {translate("for SLA processing.")}
                  </p>
                </div>

                {/* Options */}
                <div className="space-y-4 rounded-lg border border-border bg-card/50 p-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="stopOnError">{translate("Stop on error")}</Label>
                      <p className="text-xs text-muted-foreground">
                        {translate("Abort pipeline on first phase failure.")}
                      </p>
                    </div>
                    <Switch id="stopOnError" checked={stopOnError} onCheckedChange={setStopOnError} />
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="llmSummary">{translate("LLM summary")}</Label>
                      <p className="text-xs text-muted-foreground">
                        {translate("Generate AI-powered executive summary.")}
                      </p>
                    </div>
                    <Switch id="llmSummary" checked={llmSummary} onCheckedChange={setLlmSummary} />
                  </div>
                </div>

                {/* Run Button */}
                <Button
                  className="w-full"
                  size="lg"
                  onClick={handleRunPipeline}
                  disabled={isRunning || isUploadingDataFiles || isUploadingSlaFiles}
                >
                  <Play className="mr-2 h-5 w-5" />
                  {isUploadingDataFiles || isUploadingSlaFiles
                    ? translate("Uploading files...")
                    : isRunning
                      ? translate("Running pipeline...")
                      : translate("Run full pipeline")}
                </Button>
              </CardContent>
            </Card>

            {(pipelineResult || pipelineError) && (
              <Card>
                <CardHeader>
                  <CardTitle>{translate("Last pipeline response")}</CardTitle>
                  <CardDescription>
                    {!pipelineResult && pipelineError
                      ? translate("Pipeline request failed.")
                      : translate("Latest response payload")}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {pipelineError ? (
                    <div className="flex items-start gap-3 rounded-md border border-destructive/40 bg-destructive/10 p-4">
                      <AlertTriangle className="mt-0.5 h-5 w-5 text-destructive" />
                      <div className="space-y-1">
                        <p className="font-medium text-destructive">
                          {parsedPipelineError?.headline || translate("Pipeline call failed")}
                        </p>
                        {parsedPipelineError?.reason ? (
                          <p className="text-sm text-destructive/80">{parsedPipelineError.reason}</p>
                        ) : (
                          <p className="text-sm text-destructive/80">{pipelineError}</p>
                        )}
                        {parsedPipelineError?.references?.length ? (
                          <div className="pt-1">
                            <p className="text-xs font-medium text-destructive/60">{translate("Related files")}</p>
                            <ul className="mt-1 space-y-1 text-xs text-destructive/60">
                              {parsedPipelineError.references.map((reference) => (
                                <li key={reference}>
                                  <code className="break-all">{reference}</code>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                  {pipelineResult ? (
                    <div className="space-y-3">
                      <div className="rounded-md border border-border bg-muted/20 p-4">
                        <p className="text-sm font-medium text-muted-foreground">{translate("Run ID")}</p>
                        <p className="font-mono text-sm text-foreground">{pipelineResult.run_id}</p>
                      </div>
                      <div className="rounded-md border border-border bg-muted/20 p-4">
                        <p className="text-sm font-medium text-muted-foreground">{translate("Phases payload")}</p>
                        <pre className="max-h-64 overflow-auto text-xs text-foreground">
                          {JSON.stringify(pipelineResult.phases, null, 2)}
                        </pre>
                      </div>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            )}

            {/* Pipeline Stages Overview */}
            <Card>
              <CardHeader>
                <CardTitle>{translate("Pipeline stages")}</CardTitle>
                <CardDescription>{translate("10 stages from ingestion to BI delivery")}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-3 md:grid-cols-3">
                  {pipelineStageSummaries.map((phase) => (
                    <div
                      key={phase.stage}
                      className="rounded-lg border border-border bg-gradient-to-br from-card to-primary/5 p-4"
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded bg-primary text-xs font-bold text-primary-foreground">
                          {phase.stage}
                        </span>
                        <h3 className="font-semibold text-foreground">{phase.name}</h3>
                      </div>
                      <p className="text-xs text-muted-foreground">{phase.desc}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    </div>
  )
}
