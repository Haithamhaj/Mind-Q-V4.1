"use client";

import React from "react";
import clsx from "clsx";
import type { Layer3Intelligence } from "../../data/intelligence";
import type { KnimeDataSnapshot, KnimeDQResult, KnimeExport, KnimeReport } from "../../data/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExternalLink } from "lucide-react";

type KnimeResultsPanelProps = {
  data: Layer3Intelligence["knime"];
  dataset?: KnimeDataSnapshot | null;
  report?: KnimeReport | null;
  className?: string;
};

const numberFormatter = new Intl.NumberFormat("ar-SA");
const percentFormatter = new Intl.NumberFormat("ar-SA", { style: "percent", maximumFractionDigits: 1 });
const decimalFormatter = new Intl.NumberFormat("ar-SA", { maximumFractionDigits: 2 });

const formatNumber = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return numberFormatter.format(value);
};

const formatPercent = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return percentFormatter.format(value);
};

const formatDecimal = (value?: number | null) => {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return decimalFormatter.format(value);
};

const formatSize = (size?: number | null) => {
  if (!size || size <= 0) return "-";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const toNumber = (raw: unknown): number | undefined => {
  if (typeof raw === "number" && Number.isFinite(raw)) {
    return raw;
  }
  if (typeof raw === "string") {
    const parsed = Number(raw);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return undefined;
};

const pickNumber = (entry: Record<string, unknown>, keys: string[]): number | undefined => {
  for (const key of keys) {
    const value = toNumber(entry[key]);
    if (value !== undefined) {
      return value;
    }
  }
  return undefined;
};

const pickText = (entry: Record<string, unknown>, keys: string[]): string | undefined => {
  for (const key of keys) {
    const value = entry[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
};

const isFailingRule = (result: KnimeDQResult): boolean => {
  if (result.passed === false) return true;
  const status = (result.status ?? "").toString().toLowerCase();
  return ["fail", "failed", "stop"].includes(status);
};

const hasPreviewData = (columns: string[], rows: Array<Record<string, unknown>>) =>
  Boolean(columns.length && rows.length);

export const KnimeResultsPanel: React.FC<KnimeResultsPanelProps> = ({ data, dataset, report, className }) => {
  const summaryNumbers = {
    dq_rules: toNumber(data.report_summary?.dq_rules),
    dq_failed: toNumber(data.report_summary?.dq_failed),
    insight_count: toNumber(data.report_summary?.insight_count),
    export_count: toNumber(data.report_summary?.export_count),
    coverage: toNumber(data.report_summary?.coverage),
  };
  const extras = report?.extras ?? null;
  const clusterSummary = extras?.clusters?.summary ?? [];
  const clusterFeatures = extras?.clusters?.features ?? [];
  const anomalyRows = extras?.anomalies?.rows ?? [];
  const anomalyColumns = extras?.anomalies?.columns ?? [];
  const correlationPairs = extras?.correlations?.pairs ?? [];
  const forecast = extras?.forecast ?? null;

  const totalRows = dataset?.total_rows ?? data.data_parquet?.rows ?? null;
  const parquetSize = dataset?.size_bytes ?? data.data_parquet?.size_bytes;
  const parquetUpdatedAt = dataset?.updated_at ?? data.data_parquet?.updated_at;
  const previewColumns =
    dataset?.columns?.length ? dataset.columns.slice(0, 8) : data.data_parquet?.columns?.slice(0, 8) ?? [];
  const previewRows =
    dataset?.rows?.length ? dataset.rows.slice(0, Math.min(dataset.rows.length, 10)) : data.data_parquet?.preview ?? [];
  const previewLink = dataset?.run ? `/api/bi/knime-data?run=${encodeURIComponent(dataset.run)}&limit=1000` : undefined;

  const dqResults = report?.dq_report?.results ?? [];
  const failingRules = dqResults.filter(isFailingRule);
  const topFailingRules = failingRules.slice(0, 5);

  const insightItems = report?.insights?.items ?? [];
  const topInsights = insightItems.slice(0, 4);

  const exportItems = report?.exports ?? [];
  const topExports: KnimeExport[] = exportItems.slice(0, 5);

  const coverageValue =
    summaryNumbers.coverage ?? toNumber(report?.dq_coverage?.summary?.coverage) ?? undefined;

  const profileFiles = data.files ?? [];

  const layer2Payload = (report?.layer2_candidate?.payload ?? null) as Record<string, unknown> | null;
  const primaryDriver = layer2Payload
    ? (() => {
        const variance = layer2Payload.variance as Record<string, unknown> | undefined;
        if (!variance) return undefined;
        const columns = variance.columns as Array<Record<string, unknown>> | undefined;
        if (!columns?.length) return undefined;
        const first = columns[0];
        return pickText(first, ["column", "feature", "name"]);
      })()
    : undefined;

  const summaryCards = [
    { label: "قواعد الجودة", value: formatNumber(summaryNumbers.dq_rules) },
    { label: "إنذارات الجودة", value: formatNumber(summaryNumbers.dq_failed), tone: "alert" as const },
    { label: "الرؤى المكتشفة", value: formatNumber(summaryNumbers.insight_count) },
    { label: "جداول التحويل", value: formatNumber(summaryNumbers.export_count) },
    { label: "تغطية DQ", value: coverageValue !== undefined ? formatPercent(coverageValue) : "-", tone: "soft" as const },
  ];

  return (
    <Card className={clsx("border-border/40 bg-background/80 shadow-sm", className)} dir="rtl">
      <CardHeader className="flex flex-col gap-2 text-start">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="text-base font-semibold text-foreground">نتائج KNIME المحسّنة</CardTitle>
          <Badge variant="outline" className="text-xs font-medium">
            الوضع: {data.mode ?? "prompt"}
          </Badge>
        </div>
        <CardDescription className="text-sm text-muted-foreground">
          موجز لأهم مخرجات KNIME بعد مرحلة الجسر مع مقارنة ما بعد المرحلة 08 لإبراز أقوى الرؤى والملفات الجاهزة.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-xs text-muted-foreground">
        <div className="flex items-center justify-between">
          <span>Run ID</span>
          <span className="font-mono text-foreground">{data.run_id ?? "-"}</span>
        </div>

        <div className="grid gap-2 rounded-xl border border-border/60 bg-background/40 p-3 md:grid-cols-2 lg:grid-cols-5">
          {summaryCards.map((item) => (
            <div
              key={item.label}
              className={clsx(
                "flex flex-col gap-1 rounded-lg border border-border/40 px-3 py-2",
                item.tone === "alert" ? "bg-destructive/10 text-destructive-foreground" : "bg-background/60",
              )}
            >
              <span className="text-[10px] text-muted-foreground">{item.label}</span>
              <span className="text-sm font-semibold text-foreground">{item.value}</span>
            </div>
          ))}
        </div>

        {primaryDriver ? (
          <div className="rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-[11px] text-primary-foreground">
            أبرز محرك تباين: <span className="font-semibold">{primaryDriver}</span>
          </div>
        ) : null}

        <div className="grid gap-3 rounded-xl border border-border/60 bg-background/50 p-3 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-foreground">ملخص الجودة</h4>
            {topFailingRules.length ? (
              <ul className="space-y-2">
                {topFailingRules.map((result, index) => (
                  <li
                    key={result.id ?? result.title ?? `dq-${index}`}
                    className="rounded-lg border border-destructive/40 bg-destructive/5 p-2 text-[11px] text-destructive-foreground"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-foreground">{result.title ?? result.id ?? "قانون جودة"}</span>
                      <Badge variant="destructive" className="text-[10px]">
                        {result.severity ?? "تنبيه"}
                      </Badge>
                    </div>
                    {result.entity ? <p className="text-muted-foreground">الحقل: {result.entity}</p> : null}
                    <div className="flex flex-wrap items-center gap-3 text-muted-foreground">
                      {result.fail_rate !== undefined ? (
                        <span>نسبة الفشل: {formatPercent(result.fail_rate)}</span>
                      ) : null}
                      {result.failed_rows !== undefined ? (
                        <span>صفوف متأثرة: {formatNumber(result.failed_rows)}</span>
                      ) : null}
                    </div>
                    {result.notes ? <p className="text-muted-foreground">{result.notes}</p> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="rounded-lg border border-border/40 bg-background/40 p-2 text-muted-foreground">
                لا توجد مخالفات جودة بارزة.
              </p>
            )}
            {report?.dq_report?.source ? (
              <a
                href={report.dq_report.source}
                className="inline-flex items-center gap-1 text-primary underline underline-offset-4"
                target="_blank"
                rel="noopener noreferrer"
              >
                عرض تقرير الجودة الكامل
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : null}
            {report?.dq_coverage?.source ? (
              <a
                href={report.dq_coverage.source}
                className="inline-flex items-center gap-1 text-primary underline underline-offset-4"
                target="_blank"
                rel="noopener noreferrer"
              >
                تحميل ملخص التغطية
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : null}
          </div>

          <div className="flex flex-col gap-2">
            <h4 className="text-sm font-semibold text-foreground">الرؤى الإحصائية</h4>
            {topInsights.length ? (
              <ul className="space-y-2">
                {topInsights.map((insight, index) => {
                  const metric = pickText(insight as Record<string, unknown>, ["metric", "kpi", "feature"]);
                  const dimension = pickText(insight as Record<string, unknown>, ["dimension", "segment", "bucket"]);
                  const pValue = pickNumber(insight as Record<string, unknown>, ["p_value", "pValue", "p"]);
                  const effect = pickNumber(insight as Record<string, unknown>, ["effect_size", "lift", "impact"]);
                  const sample = pickNumber(insight as Record<string, unknown>, ["n", "support", "samples"]);
                  const rejected = Boolean(insight["fdr_rejected"]);
                  const insightId =
                    pickText(insight as Record<string, unknown>, ["id", "insight_id"]) ??
                    insight.headline ??
                    metric ??
                    `insight-${index}`;
                  return (
                    <li
                      key={insightId}
                      className="rounded-lg border border-border/40 bg-background/40 p-2 text-[11px] text-muted-foreground"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <p className="font-medium text-foreground">{insight.headline ?? "رؤية مكتشفة"}</p>
                          <div className="flex flex-wrap items-center gap-2">
                            {metric ? <span>المؤشر: {metric}</span> : null}
                            {dimension ? <span>البعد: {dimension}</span> : null}
                          </div>
                        </div>
                        {rejected ? (
                          <Badge variant="outline" className="border-emerald-400 text-[10px] text-emerald-500">
                            موثوقة (FDR)
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-3">
                        {pValue !== undefined ? <span>p-value: {formatDecimal(pValue)}</span> : null}
                        {effect !== undefined ? <span>التأثير: {formatDecimal(effect)}</span> : null}
                        {sample !== undefined ? <span>حجم العينة: {formatNumber(sample)}</span> : null}
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="rounded-lg border border-border/40 bg-background/40 p-2 text-muted-foreground">
                لم يتم تحميل رؤى إحصائية من KNIME بعد.
              </p>
            )}
            {report?.insights?.source ? (
              <a
                href={report.insights.source}
                className="inline-flex items-center gap-1 text-primary underline underline-offset-4"
                target="_blank"
                rel="noopener noreferrer"
              >
                تحميل ملف الرؤى بصيغة JSON
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : null}
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-foreground">الجداول المصدّرة</h4>
          {topExports.length ? (
            <div className="grid gap-2 md:grid-cols-2">
              {topExports.map((item) => (
                <div
                  key={item.path}
                  className="flex flex-col gap-1 rounded-lg border border-border/40 bg-background/50 p-3 text-[11px]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-foreground">
                      {item.table ?? item.relative_path ?? item.path.split("/").pop()}
                    </span>
                    <Badge variant="outline" className="text-[10px]">
                      {item.format?.toUpperCase() ?? "FILE"}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-muted-foreground">
                    {item.domain ? <span>النطاق: {item.domain}</span> : null}
                    {item.version ? <span>الإصدار: v{item.version}</span> : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-muted-foreground">
                    {item.rows !== undefined ? <span>الصفوف: {formatNumber(item.rows)}</span> : null}
                    {item.columns?.length ? <span>الأعمدة: {item.columns.length}</span> : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-muted-foreground">
                    <span>الحجم: {formatSize(item.size_bytes)}</span>
                    <span>
                      آخر تحديث:{" "}
                      {item.updated_at ? new Date(item.updated_at).toLocaleString("ar-SA") : "غير متاح"}
                    </span>
                  </div>
                  <a
                    href={item.path}
                    className="inline-flex items-center gap-1 text-primary underline underline-offset-4"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    تحميل الملف
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              ))}
            </div>
          ) : (
            <p className="rounded-lg border border-border/40 bg-background/40 p-2 text-muted-foreground">
              لا توجد ملفات تصدير متاحة بعد. نفّذ workflow KNIME لإنتاج جداول التحويل.
            </p>
          )}
        </div>

        {clusterSummary.length ? (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground">شرائح KMeans المقترحة</h4>
            <p className="text-[11px] text-muted-foreground">
              تم حساب التجزئة اعتماداً على الأعمدة: {clusterFeatures.join(", ")}
            </p>
            <div className="overflow-x-auto rounded-xl border border-border/40 bg-background/40">
              <table className="min-w-full table-auto border-separate border-spacing-y-1 text-xs">
                <thead>
                  <tr>
                    <th className="rounded-lg bg-muted px-3 py-2 text-start font-semibold text-muted-foreground">القطعة</th>
                    <th className="rounded-lg bg-muted px-3 py-2 text-start font-semibold text-muted-foreground">عدد السجلات</th>
                    <th className="rounded-lg bg-muted px-3 py-2 text-start font-semibold text-muted-foreground">الحصة</th>
                    {clusterSummary.some((item) => item.avg_lead_time_hours !== undefined) ? (
                      <th className="rounded-lg bg-muted px-3 py-2 text-start font-semibold text-muted-foreground">متوسط زمن التسليم</th>
                    ) : null}
                    {clusterSummary.some((item) => item.avg_cod_amount !== undefined) ? (
                      <th className="rounded-lg bg-muted px-3 py-2 text-start font-semibold text-muted-foreground">متوسط COD</th>
                    ) : null}
                  </tr>
                </thead>
                <tbody>
                  {clusterSummary.map((row) => (
                    <tr key={`cluster-${row.cluster}`} className="rounded-lg">
                      <td className="rounded-lg bg-background/70 px-3 py-2 text-foreground">#{row.cluster + 1}</td>
                      <td className="rounded-lg bg-background/70 px-3 py-2 text-foreground">{formatNumber(row.records)}</td>
                      <td className="rounded-lg bg-background/70 px-3 py-2 text-foreground">{formatPercent(row.share)}</td>
                      {clusterSummary.some((item) => item.avg_lead_time_hours !== undefined) ? (
                        <td className="rounded-lg bg-background/70 px-3 py-2 text-foreground">
                          {row.avg_lead_time_hours !== undefined ? formatDecimal(row.avg_lead_time_hours) : "-"}
                        </td>
                      ) : null}
                      {clusterSummary.some((item) => item.avg_cod_amount !== undefined) ? (
                        <td className="rounded-lg bg-background/70 px-3 py-2 text-foreground">
                          {row.avg_cod_amount !== undefined ? formatDecimal(row.avg_cod_amount) : "-"}
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {anomalyRows.length ? (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground">الشحنات الشاذّة المرصودة</h4>
            <p className="text-[11px] text-muted-foreground">
              أدنى قيم score تعبّر عن أعلى احتمالية شذوذ بناءً على خصائص الطلب.
            </p>
            <div className="overflow-x-auto rounded-xl border border-border/40 bg-background/40">
              <table className="min-w-full table-auto border-separate border-spacing-y-1 text-xs">
                <thead>
                  <tr>
                    {anomalyColumns.map((column) => (
                      <th key={`anomaly-col-${column}`} className="rounded-lg bg-muted px-3 py-2 text-start font-semibold text-muted-foreground">
                        {column}
                      </th>
                    ))}
                    <th className="rounded-lg bg-muted px-3 py-2 text-start font-semibold text-muted-foreground">score</th>
                  </tr>
                </thead>
                <tbody>
                  {anomalyRows.slice(0, 10).map((row, index) => (
                    <tr key={`anomaly-${index}`} className="rounded-lg">
                      {anomalyColumns.map((column) => (
                        <td key={`anomaly-${index}-${column}`} className="rounded-lg bg-background/70 px-3 py-2 text-foreground">
                          {row?.[column] !== undefined && row?.[column] !== null ? String(row[column]) : "-"}
                        </td>
                      ))}
                      <td className="rounded-lg bg-background/70 px-3 py-2 text-foreground">
                        {row?.score !== undefined && typeof row.score === "number" ? formatDecimal(row.score) : row?.score ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {correlationPairs.length ? (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground">أقوى الارتباطات</h4>
            <ul className="space-y-1 text-[11px] text-muted-foreground">
              {correlationPairs.slice(0, 10).map((pair, index) => (
                <li key={`corr-${index}`} className="rounded-lg border border-border/40 bg-background/40 px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-foreground">
                    <span>
                      {pair.feature_a} ↔ {pair.feature_b}
                    </span>
                    <span>{formatDecimal(pair.correlation)}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {forecast && forecast.predictions.length ? (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground">توقعات الطلب القصيرة</h4>
            <p className="text-[11px] text-muted-foreground">
              تم استخدام متوسط آخر {forecast.window_used ?? forecast.history.length} أيام لتقدير {forecast.metric}.
            </p>
            <div className="flex flex-col gap-2 rounded-xl border border-border/40 bg-background/40 p-3 text-[11px] text-muted-foreground">
              <div>
                <span className="font-semibold text-foreground">التاريخ الأخيرة:</span>
                <ul className="mt-1 space-y-1">
                  {forecast.history.slice(-5).map((point) => (
                    <li key={`hist-${point.timestamp}`}>
                      {point.timestamp}: {formatNumber(point.value)}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="font-semibold text-foreground">التوقعات:</span>
                <ul className="mt-1 space-y-1">
                  {forecast.predictions.map((point) => (
                    <li key={`pred-${point.timestamp}`}>
                      {point.timestamp}: {formatNumber(point.value)}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ) : null}

        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-foreground">ملفات الملف الشخصي</h4>
          {profileFiles.length ? (
            <ul className="space-y-2">
              {profileFiles.map((file) => (
                <li
                  key={file.path}
                  className="flex flex-col gap-1 rounded-xl border border-border/60 bg-background/60 p-3 text-xs text-start"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-foreground">{file.name}</span>
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <span>{formatSize(file.size_bytes)}</span>
                      {file.updated_at ? <span>{new Date(file.updated_at).toLocaleString("ar-SA")}</span> : null}
                      <ExternalLink className="h-3.5 w-3.5 opacity-60" />
                    </div>
                  </div>
                  <a
                    href={file.path}
                    className="text-primary underline underline-offset-4"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    فتح الملف
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-lg border border-border/40 bg-background/40 p-2 text-muted-foreground">
              لم يتم العثور على ملفات في مجلد الملف الشخصي.
            </p>
          )}
        </div>

        {report?.notes?.run_summary ? (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-foreground">ملخص التنفيذ</h4>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg border border-border/40 bg-background/50 p-3 text-[11px] text-muted-foreground">
              {report.notes.run_summary}
            </pre>
            {report.notes.source ? (
              <a
                href={report.notes.source}
                className="inline-flex items-center gap-1 text-primary underline underline-offset-4"
                target="_blank"
                rel="noopener noreferrer"
              >
                فتح ملف الملخص
                <ExternalLink className="h-3 w-3" />
              </a>
            ) : null}
          </div>
        ) : null}

        <div className="space-y-2 pt-1">
          <h4 className="text-sm font-semibold text-foreground">معاينة البيانات الأساسية</h4>
          {hasPreviewData(previewColumns, previewRows) ? (
            <div className="overflow-x-auto">
              <table className="min-w-full table-auto border-separate border-spacing-y-1 text-start text-xs">
                <thead>
                  <tr>
                    {previewColumns.map((column) => (
                      <th key={column} className="rounded-lg bg-muted px-3 py-2 font-semibold text-muted-foreground">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row, rowIndex) => (
                    <tr key={rowIndex} className="rounded-lg">
                      {previewColumns.map((column) => (
                        <td key={column} className="rounded-lg bg-background/70 px-3 py-2 text-foreground">
                          {row?.[column] !== undefined && row?.[column] !== null ? String(row[column]) : "-"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="rounded-xl border border-border/60 bg-background/40 p-3 text-xs text-muted-foreground">
              لم يتم تحميل معاينة البيانات. يرجى التأكد من تنفيذ KNIME Bridge أو تحميل الملف يدويًا.
            </p>
          )}
          <div className="grid gap-2 rounded-xl border border-border/50 bg-background/40 p-3 text-xs text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>عدد الصفوف</span>
              <span className="font-semibold text-foreground">{totalRows ?? "-"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>عدد الأعمدة</span>
              <span className="font-medium text-foreground">
                {previewColumns.length || data.data_parquet?.columns?.length || "-"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>تاريخ آخر تحديث</span>
              <span>{parquetUpdatedAt ? new Date(parquetUpdatedAt).toLocaleString("ar-SA") : "-"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>حجم الملف</span>
              <span>{formatSize(parquetSize)}</span>
            </div>
            {previewLink ? (
              <a
                href={previewLink}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline underline-offset-4"
              >
                تنزيل المعاينة الكاملة (JSON)
              </a>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default KnimeResultsPanel;
