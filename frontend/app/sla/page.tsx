"use client"

import React, { useCallback, useEffect, useMemo, useState } from "react"

import { Sidebar } from "@/components/sidebar"
import { Header } from "@/components/header"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useLanguage } from "@/context/language-context"
import { api, PipelineRunInfo } from "@/lib/api"
import { AlertCircle, CheckCircle2, Download, Loader2, RefreshCw, XCircle } from "lucide-react"

type MetricStatus = "pass" | "warn" | "stop" | "unknown"

interface SlaSummary {
  compliance_pct: number | null
  status: MetricStatus
  documents_total: number
  terms_total: number
  warn_terms: number
  stop_terms: number
  documents_with_warnings: number
  documents_without_terms: number
  last_execution?: string | null
  execution_seconds?: number | null
  narrative?: string | null
  recommendations?: string[]
}

interface SlaKpiRef {
  kpi_id: string
  label?: string | null
  status?: MetricStatus
  value_pct?: number | null
  warn_threshold_pct?: number | null
  stop_threshold_pct?: number | null
}

interface SlaKpi {
  id: string
  label?: string
  value_pct?: number | null
  raw_value?: number | null
  unit?: string | null
  status: MetricStatus
  warn_threshold_pct?: number | null
  stop_threshold_pct?: number | null
  document_id?: string | null
  reason?: string | null
}

interface SlaDocumentCard {
  id?: string | null
  title?: string | null
  display_name?: string | null
  type?: string | null
  status: MetricStatus
  compliance_pct?: number | null
  term_counts?: {
    extracted?: number
    evaluated?: number
    passed?: number
    warn?: number
    stop?: number
  }
  kpi_refs?: SlaKpiRef[]
  notes?: string[]
  excerpt?: string | null
}

interface SlaAlert {
  id: string
  category: string
  severity: "info" | "warning" | "critical"
  message: string
  recommendation?: string | null
}

interface SlaAttachment {
  name: string
  document_id?: string | null
  media_type?: string | null
  size_bytes?: number | null
  normalized_path?: string | null
  stored_path?: string | null
}

interface SlaMetadata {
  run_id?: string
  generated_at?: string
  sources?: Record<string, unknown>
  next_actions?: Array<{ message: string; category?: string; severity?: string }>
}

interface SlaPayload {
  run: string
  summary: SlaSummary
  documents: SlaDocumentCard[]
  kpis: SlaKpi[]
  alerts: SlaAlert[]
  attachments: SlaAttachment[]
  metadata?: SlaMetadata
}

const STATUS_CONFIG: Record<MetricStatus, { badge: string; tint: string; icon: JSX.Element }> = {
  pass: { badge: "bg-emerald-500/20 text-emerald-600 border-emerald-500/40", tint: "text-emerald-600", icon: <CheckCircle2 className="h-4 w-4" /> },
  warn: { badge: "bg-amber-500/20 text-amber-600 border-amber-500/40", tint: "text-amber-600", icon: <AlertCircle className="h-4 w-4" /> },
  stop: { badge: "bg-destructive/20 text-destructive border-destructive/30", tint: "text-destructive", icon: <XCircle className="h-4 w-4" /> },
  unknown: { badge: "bg-muted text-muted-foreground", tint: "text-muted-foreground", icon: <AlertCircle className="h-4 w-4" /> },
}

const formatNumber = (value: number | null | undefined, fractionDigits = 2) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-"
  return value.toLocaleString(undefined, { maximumFractionDigits: fractionDigits })
}

const formatDuration = (seconds: number | null | undefined) => {
  if (!seconds) return "-"
  if (seconds < 60) return `${Math.round(seconds)} s`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} min`
  return `${(seconds / 3600).toFixed(1)} h`
}

const formatDate = (value?: string | null, locale = "ar-SA") => {
  if (!value) return "-"
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date)
  } catch {
    return value
  }
}

const documentTypeLabel = (value?: string | null, translate?: (key: string) => string) => {
  if (!value) return translate ? translate("Other") : "Other"
  const map: Record<string, string> = {
    supplier_contract: "عقد مورد",
    delivery_agreement: "اتفاقية توصيل",
    operations_policy: "سياسة تشغيل",
    operations_procedure: "إجراء تشغيلي",
    service_level: "اتفاقية SLA",
    other: "ملف تشغيلي",
  }
  return translate ? translate(map[value] || map.other) : map[value] || map.other
}

const statusLabel = (status: MetricStatus, translate: (key: string) => string) => {
  const labels: Record<MetricStatus, string> = {
    pass: "داخل الحد",
    warn: "تحذير",
    stop: "إيقاف",
    unknown: "غير محدد",
  }
  return translate(labels[status])
}

const SlaPage: React.FC = () => {
  const { translate } = useLanguage()
  const [runs, setRuns] = useState<PipelineRunInfo[]>([])
  const [selectedRun, setSelectedRun] = useState<string | undefined>()
  const [runsLoading, setRunsLoading] = useState(false)
  const [runsError, setRunsError] = useState<string | undefined>()
  const [slaData, setSlaData] = useState<SlaPayload | undefined>()
  const [slaLoading, setSlaLoading] = useState(false)
  const [slaError, setSlaError] = useState<string | undefined>()
  const [refreshToken, setRefreshToken] = useState(0)

  const currentRunParam = selectedRun ?? "run-latest"

  const loadRuns = useCallback(async () => {
    setRunsLoading(true)
    setRunsError(undefined)
    try {
      const response = await api.listRuns()
      setRuns(response.runs ?? [])
    } catch (error) {
      setRunsError(error instanceof Error ? error.message : translate("تعذر تحميل قائمة التشغيل."))
    } finally {
      setRunsLoading(false)
    }
  }, [translate])

  const loadSlaData = useCallback(async () => {
    setSlaLoading(true)
    setSlaError(undefined)
    try {
      const response = await fetch(`/api/bi/sla?run=${encodeURIComponent(currentRunParam)}`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const payload = (await response.json()) as SlaPayload
      setSlaData(payload)
    } catch (error) {
      setSlaError(error instanceof Error ? error.message : translate("تعذر تحميل مؤشرات الامتثال."))
      setSlaData(undefined)
    } finally {
      setSlaLoading(false)
    }
  }, [currentRunParam, translate])

  useEffect(() => {
    loadRuns().catch(() => undefined)
  }, [loadRuns])

  useEffect(() => {
    loadSlaData().catch(() => undefined)
  }, [loadSlaData, refreshToken])

  const handleRefresh = () => setRefreshToken((value) => value + 1)

  const summary = slaData?.summary
  const summaryRecommendations = summary?.recommendations
  const kpis = slaData?.kpis ?? []
  const documents = slaData?.documents ?? []
  const rawAlerts = slaData?.alerts
  const alerts = useMemo(() => (Array.isArray(rawAlerts) ? rawAlerts : []), [rawAlerts])
  const rawAttachments = slaData?.attachments
  const attachments = useMemo(() => (Array.isArray(rawAttachments) ? rawAttachments : []), [rawAttachments])
  const metadata = slaData?.metadata
  const metadataNextActions = metadata?.next_actions

  const nextActions = useMemo(() => {
    const recommendations: string[] = []
    if (Array.isArray(summaryRecommendations)) {
      summaryRecommendations.forEach((item) => {
        if (item) recommendations.push(item)
      })
    }
    if (Array.isArray(metadataNextActions)) {
      metadataNextActions.forEach((action) => {
        if (action?.message) recommendations.push(action.message)
      })
    }
    const fromAlerts =
      Array.isArray(alerts) ?
        alerts
          .filter((alert) => Boolean(alert?.recommendation))
          .map((alert) => alert?.recommendation as string) :
        []
    recommendations.push(...fromAlerts)
    return Array.from(new Set(recommendations.filter(Boolean))).slice(0, 5)
  }, [alerts, metadataNextActions, summaryRecommendations])

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <main className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h1 className="text-2xl font-semibold">{translate("لوحة امتثال SLA")}</h1>
                {summary?.last_execution && (
                  <p className="text-sm text-muted-foreground">
                    {translate("آخر تحديث: {value}", { value: formatDate(summary.last_execution) })}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Select value={currentRunParam} onValueChange={(value) => setSelectedRun(value === "run-latest" ? undefined : value)}>
                  <SelectTrigger className="w-[220px]">
                    <SelectValue placeholder={translate("حدد التشغيل")}>
                      {runsLoading ? translate("جارٍ التحميل...") : translate("تشغيل: {run}", { run: currentRunParam })}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="run-latest">{translate("أحدث تشغيل")}</SelectItem>
                    {runs.map((run) => (
                      <SelectItem key={run.run_id} value={run.run_id}>
                        {run.run_id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" onClick={handleRefresh} disabled={slaLoading}>
                  {slaLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                  {translate("تحديث")}
                </Button>
              </div>
            </div>

            {runsError && <Card className="border-destructive/40 bg-destructive/10 text-destructive">
              <CardContent className="py-4 text-sm">{runsError}</CardContent>
            </Card>}
            {slaError && <Card className="border-destructive/40 bg-destructive/10 text-destructive">
              <CardContent className="py-4 text-sm">{slaError}</CardContent>
            </Card>}

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle>{translate("درجة الامتثال العامة")}</CardTitle>
                  <CardDescription>{translate("ملخص سريع لحالة SLA الحالية")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="text-4xl font-semibold">{formatNumber(summary?.compliance_pct, 1)}%</div>
                    <Badge className={STATUS_CONFIG[summary?.status ?? "unknown"].badge}>
                      {summary ? statusLabel(summary.status, translate) : translate("غير متاح")}
                    </Badge>
                  </div>
                  <dl className="grid grid-cols-2 gap-3 text-sm text-muted-foreground">
                    <div>
                      <dt>{translate("عدد الوثائق")}</dt>
                      <dd className="font-medium text-foreground">{summary?.documents_total ?? 0}</dd>
                    </div>
                    <div>
                      <dt>{translate("عدد البنود")}</dt>
                      <dd className="font-medium text-foreground">{summary?.terms_total ?? 0}</dd>
                    </div>
                    <div>
                      <dt>{translate("بنود تحذيرية")}</dt>
                      <dd className="font-medium text-amber-600">{summary?.warn_terms ?? 0}</dd>
                    </div>
                    <div>
                      <dt>{translate("بنود إيقاف")}</dt>
                      <dd className="font-medium text-destructive">{summary?.stop_terms ?? 0}</dd>
                    </div>
                  </dl>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{translate("مدة التنفيذ")}</span>
                    <span>{formatDuration(summary?.execution_seconds ?? slaData?.performance?.exec_seconds ?? null)}</span>
                  </div>
                </CardContent>
              </Card>

              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle>{translate("ملخص تنفيذي")}</CardTitle>
                  <CardDescription>{translate("ملخص قابل للقراءة + توصيات")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {summary?.narrative || translate("لم يتم توفير سرد تنفيذي لهذا التشغيل.")}
                  </p>
                  {nextActions.length > 0 && (
                    <div>
                      <h3 className="mb-2 text-sm font-medium">{translate("التوصيات القادمة")}</h3>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                    {nextActions.map((action, index) => (
                      <li key={`${index}-${action}`}>{action}</li>
                    ))}
                      </ul>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>{translate("الوثائق ومؤشرات الامتثال")}</CardTitle>
                <CardDescription>{translate("نظرة شاملة على الملفات المرفوعة")}</CardDescription>
              </CardHeader>
              <CardContent>
                {documents.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{translate("لا توجد مستندات SLA لهذا التشغيل.")}</p>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {documents.map((document) => {
                      const status = document.status ?? "unknown"
                      const statusConfig = STATUS_CONFIG[status]
                      const compliance = document.compliance_pct
                      const termCounts = document.term_counts || {}
                      return (
                        <div key={document.id ?? document.title} className="rounded-xl border border-border/40 bg-card/50 p-4 shadow-sm transition hover:shadow-md">
                          <div className="flex items-start justify-between gap-3">
                            <div className="space-y-1">
                              <h3 className="text-sm font-semibold text-foreground">{document.display_name || document.title || translate("وثيقة")}</h3>
                              <p className="text-xs text-muted-foreground">{documentTypeLabel(document.type, translate)}</p>
                            </div>
                            <Badge className={statusConfig.badge}>{statusLabel(status, translate)}</Badge>
                          </div>
                          <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-muted-foreground">
                            <div>
                      <dt>{translate("معدل الامتثال")}</dt>
                      <dd className="text-sm font-medium text-foreground">
                        {compliance !== undefined && compliance !== null ? `${compliance.toFixed(1)}%` : "-"}
                      </dd>
                            </div>
                            <div>
                              <dt>{translate("بنود متطابقة")}</dt>
                              <dd className="text-sm font-medium text-foreground">{termCounts.passed ?? 0}/{termCounts.evaluated ?? 0}</dd>
                            </div>
                            <div>
                              <dt>{translate("تنبيهات")}</dt>
                              <dd className="text-sm font-medium text-foreground">{(termCounts.warn ?? 0) + (termCounts.stop ?? 0)}</dd>
                            </div>
                          </dl>
                          {document.kpi_refs && document.kpi_refs.length > 0 && (
                            <div className="mt-3 rounded-lg border border-border/40 bg-muted/30 p-2">
                              <p className="text-xs font-medium text-muted-foreground">{translate("المؤشرات المرتبطة")}</p>
                              <ul className="mt-1 space-y-1 text-xs">
                                {document.kpi_refs.map((ref) => (
                                  <li key={`${document.id ?? document.title ?? "doc"}-${ref.kpi_id}`} className="flex items-center gap-2">
                                    <span className="font-medium text-foreground">{ref.label || ref.kpi_id}</span>
                                    {ref.value_pct !== undefined && ref.value_pct !== null && (
                                      <span className="text-muted-foreground">{ref.value_pct.toFixed(1)}%</span>
                                    )}
                                    {ref.status && <Badge variant="outline" className={STATUS_CONFIG[ref.status].badge}>{statusLabel(ref.status, translate)}</Badge>}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {document.excerpt && (
                            <p className="mt-3 line-clamp-3 text-xs text-muted-foreground">{document.excerpt}</p>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{translate("مؤشرات SLA الرئيسية")}</CardTitle>
                <CardDescription>{translate("مقارنة القيم الحالية بالحدود")}</CardDescription>
              </CardHeader>
              <CardContent>
                {kpis.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{translate("لم يتم احتساب مؤشرات SLA لهذا التشغيل.")}</p>
                ) : (
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {kpis.map((kpi) => {
                      const config = STATUS_CONFIG[kpi.status]
                      return (
                        <div key={kpi.id} className="rounded-xl border border-border/40 bg-card/50 p-4 shadow-sm transition hover:shadow-md">
                          <div className="flex items-start justify-between gap-3">
                            <div className="space-y-1">
                              <h3 className="text-sm font-semibold text-foreground">{kpi.label || kpi.id}</h3>
                              {kpi.reason && <p className="text-xs text-muted-foreground">{kpi.reason}</p>}
                            </div>
                            <Badge className={config.badge}>{statusLabel(kpi.status, translate)}</Badge>
                          </div>
                          <div className="mt-3 text-2xl font-semibold text-foreground">
                            {kpi.value_pct !== undefined && kpi.value_pct !== null ? `${kpi.value_pct.toFixed(1)}%` : formatNumber(kpi.raw_value)}
                          </div>
                          <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-muted-foreground">
                            <div>
                              <dt>{translate("حد التحذير")}</dt>
                              <dd>{kpi.warn_threshold_pct !== undefined && kpi.warn_threshold_pct !== null ? `${kpi.warn_threshold_pct.toFixed(1)}%` : "-"}</dd>
                            </div>
                            <div>
                              <dt>{translate("حد الإيقاف")}</dt>
                              <dd>{kpi.stop_threshold_pct !== undefined && kpi.stop_threshold_pct !== null ? `${kpi.stop_threshold_pct.toFixed(1)}%` : "-"}</dd>
                            </div>
                          </dl>
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{translate("التنبيهات")}</CardTitle>
                <CardDescription>{translate("تصنيف تحذيرات البيانات والبنود")}</CardDescription>
              </CardHeader>
              <CardContent>
                {alerts.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{translate("لا توجد تنبيهات لهذا التشغيل.")}</p>
                ) : (
                  <div className="space-y-3">
                    {alerts.map((alert) => (
                      <div key={alert.id} className="rounded-lg border border-border/40 bg-muted/20 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-medium text-foreground">{alert.message}</p>
                            {alert.recommendation && <p className="mt-1 text-xs text-muted-foreground">{alert.recommendation}</p>}
                          </div>
                          <Badge variant="outline">{translate(alert.category)}</Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{translate("المرفقات الخام")}</CardTitle>
                <CardDescription>{translate("قائمة الملفات المتاحة للتنزيل")}</CardDescription>
              </CardHeader>
              <CardContent>
                {attachments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{translate("لا توجد مرفقات متاحة.")}</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b border-border/40 text-left text-xs uppercase text-muted-foreground">
                        <tr>
                          <th className="px-2 py-2">{translate("الملف")}</th>
                          <th className="px-2 py-2">{translate("النوع")}</th>
                          <th className="px-2 py-2">{translate("الحجم")}</th>
                          <th className="px-2 py-2" />
                        </tr>
                      </thead>
                      <tbody>
                        {attachments.map((attachment) => (
                          <tr key={attachment.normalized_path ?? attachment.name} className="border-b border-border/20 last:border-0">
                            <td className="px-2 py-2 font-medium">{attachment.name}</td>
                            <td className="px-2 py-2 text-muted-foreground">{attachment.media_type ?? "-"}</td>
                            <td className="px-2 py-2 text-muted-foreground">
                              {attachment.size_bytes ? `${(attachment.size_bytes / 1024).toFixed(1)} KB` : "-"}
                            </td>
                            <td className="px-2 py-2 text-right">
                              {attachment.stored_path ? (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-muted-foreground"
                                  onClick={() => {
                                    const url = `/api/mindq/v1/runs/${encodeURIComponent(currentRunParam)}/artifacts/content?path=${encodeURIComponent(attachment.stored_path ?? "")}`
                                    window.open(url, "_blank")
                                  }}
                                >
                                  <Download className="mr-2 h-4 w-4" />
                                  {translate("تحميل")}
                                </Button>
                              ) : (
                                <span className="text-xs text-muted-foreground">{translate("غير متاح")}</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    </div>
  )
}

export default SlaPage
