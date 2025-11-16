"use client";

import React from "react";
import clsx from "clsx";
import type { Layer3Intelligence } from "../../data/intelligence";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import NetworkGraph from "./NetworkGraph";
import SankeyChart from "./SankeyChart";
import AnomalyTimelineChart from "./AnomalyTimelineChart";
import PredictiveTrendsChart from "./PredictiveTrendsChart";

const formatCount = (value: unknown): string => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toLocaleString("ar-SA");
  }
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return "-";
};

const extractColumnNames = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((entry) => {
      if (!entry || typeof entry !== "object") return undefined;
      const record = entry as Record<string, unknown>;
      const primary = record.name ?? record.original_name ?? record.standardized_name;
      return typeof primary === "string" ? primary : undefined;
    })
    .filter((name): name is string => Boolean(name));
};

type Layer3IntelligencePanelProps = {
  intelligence: Layer3Intelligence;
  className?: string;
};

export const Layer3IntelligencePanel: React.FC<Layer3IntelligencePanelProps> = ({ intelligence, className }) => {
  const anomalyCount = intelligence.anomalies.anomalies.length;
  const gate = intelligence.business_validation?.gate;
  const diagnostics = intelligence.business_validation?.diagnostics;
  const decisionCounts =
    (gate?.counts as Record<string, unknown> | undefined) ??
    (diagnostics?.decision_counts as Record<string, unknown> | undefined);
  const gateStatus = gate?.status?.toUpperCase() ?? "PASS";
  const gateReasons = gate?.reasons ?? [];
  const gateWarnings = gate?.warnings ?? [];
  const nzvImpact =
    gate?.nzv_impact ??
    ((diagnostics?.nzv_impact as Record<string, unknown> | undefined) ??
      ((intelligence.business_validation?.data_health?.nzv_impact as Record<string, unknown> | undefined) ?? undefined));
  const lowVarianceColumns = nzvImpact ? extractColumnNames(nzvImpact.low_variance_ignored_columns) : [];
  const advancedSummary = intelligence.advanced?.summary as Record<string, unknown> | undefined;
  const advancedSources = advancedSummary?.sources as
    | Record<string, { path?: string; source?: string }>
    | undefined;
  const advancedSourceEntries = advancedSources ? Object.entries(advancedSources) : [];
  const forecastPreview = intelligence.advanced?.orders_forecast?.preview ?? [];
  const forecastHeaders = forecastPreview.length ? Object.keys(forecastPreview[0]).slice(0, 4) : [];
  const forecastRows = forecastPreview.slice(0, 4);
  const forecastError = intelligence.advanced?.orders_forecast?.error;
  const forecastRowsCount = intelligence.advanced?.orders_forecast?.rows;

  const gateBadgeVariant =
    gateStatus === "STOP" ? "destructive" : gateStatus === "WARN" ? "outline" : "secondary";
  const gateStatusLabel =
    gateStatus === "STOP" ? "إيقاف" : gateStatus === "WARN" ? "تحذير" : "جاهزية";

  return (
    <section
      className={clsx(
        "flex flex-col gap-6 rounded-2xl border border-border/60 bg-background/70 p-4 shadow-sm",
        className,
      )}
      dir="rtl"
    >
      <header className="flex flex-col gap-2 text-start">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-foreground">تحليلات الطبقة الثالثة</h2>
            <p className="text-sm text-muted-foreground">
              تمثيل الشبكات، تدفقات التأثير، ملخصات الجاهزية (Stage 09)، وملفات التحليلات المتقدمة التي تُنشئها مرحلة Stage
              08.
            </p>
          </div>
          <Badge variant="secondary" className="text-xs font-medium">
            Run: {intelligence.run}
          </Badge>
        </div>
      </header>

      {(gate || intelligence.advanced) && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {gate ? (
            <Card className="border-border/40 bg-background/80 shadow-sm">
              <CardHeader className="pb-3 text-start">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-base font-semibold">بوابة الجاهزية (Stage 09)</CardTitle>
                    <CardDescription className="text-sm text-muted-foreground">
                      حالة التحذيرات، أسباب التوقف، وأثر أعمدة NZV على القرارات.
                    </CardDescription>
                  </div>
                  <Badge variant={gateBadgeVariant} className="text-xs font-medium">
                    {gateStatusLabel}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                {gateReasons.length ? (
                  <ul className="space-y-1 text-start">
                    {gateReasons.slice(0, 4).map((reason) => (
                      <li key={reason} className="text-xs text-foreground">
                        • {reason}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">لا توجد أسباب إضافية مسجلة.</p>
                )}
                <div className="grid grid-cols-2 gap-2 text-xs text-start">
                  <div className="rounded-md border border-border/60 bg-background/70 p-2">
                    <p className="text-muted-foreground">مقبول</p>
                    <p className="text-lg font-semibold text-foreground">{formatCount(decisionCounts?.approve)}</p>
                  </div>
                  <div className="rounded-md border border-border/60 bg-background/70 p-2">
                    <p className="text-muted-foreground">مرفوض</p>
                    <p className="text-lg font-semibold text-foreground">{formatCount(decisionCounts?.reject)}</p>
                  </div>
                </div>
                {lowVarianceColumns.length ? (
                  <div className="text-xs text-start">
                    <p className="text-muted-foreground">أعمدة NZV الخاضعة للمتابعة</p>
                    <p className="text-foreground">{lowVarianceColumns.slice(0, 5).join("، ")}</p>
                  </div>
                ) : null}
                {gateWarnings.length ? (
                  <div className="text-xs text-start">
                    <p className="text-muted-foreground">تحذيرات إضافية</p>
                    <ul className="space-y-1">
                      {gateWarnings.slice(0, 3).map((warning) => (
                        <li key={warning}>• {warning}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {intelligence.advanced ? (
            <Card className="border-border/40 bg-background/80 shadow-sm">
              <CardHeader className="pb-3 text-start">
                <CardTitle className="text-base font-semibold">ملف التحليلات المتقدمة (Stage 08)</CardTitle>
                <CardDescription className="text-sm text-muted-foreground">
                  ملخص عن ملفات `advanced/` بما في ذلك التجمعات، الانحرافات، وتوقعات الطلب.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-muted-foreground">
                {advancedSourceEntries.length ? (
                  <ul className="space-y-1 text-xs text-start">
                    {advancedSourceEntries.slice(0, 4).map(([name, meta]) => (
                      <li key={name} className="text-foreground">
                        • {name.replaceAll("_", " ")} – {meta?.source ?? "python"}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">لا تتوفر مصادر موثقة في `summary.json`.</p>
                )}
                {forecastError ? (
                  <p className="text-xs text-destructive">تعذّر تحميل ملف التوقعات: {forecastError}</p>
                ) : (
                  <>
                    <div className="text-xs text-start">
                      <p className="text-muted-foreground">صفوف التوقع</p>
                      <p className="text-foreground">{formatCount(forecastRowsCount ?? forecastRows.length)}</p>
                    </div>
                    {forecastHeaders.length ? (
                      <div className="overflow-x-auto rounded-md border border-border/60">
                        <table className="min-w-full divide-y divide-border/60 text-xs">
                          <thead className="bg-muted/30 text-foreground">
                            <tr>
                              {forecastHeaders.map((header) => (
                                <th key={header} className="px-2 py-1 text-start font-medium">
                                  {header}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/40">
                            {forecastRows.map((row, index) => (
                              <tr key={`forecast-row-${index}`}>
                                {forecastHeaders.map((header) => (
                                  <td key={`${header}-${index}`} className="px-2 py-1 text-foreground">
                                    {String(row[header] ?? "-")}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground">لا تتوفر معاينة للتوقعات.</p>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          ) : null}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="border-border/40 bg-background/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-start">شبكة التأثير</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              KPIs والعوامل الأعلى تأثيراً مع قوة الإشارة المكتشفة.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <NetworkGraph data={intelligence.network} />
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-background/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-start">تدفقات التأثير</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              انتقال الإشارات من KPIs إلى شرائح التشغيل وفق تغطية Stage 08.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SankeyChart data={intelligence.sankey} />
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-background/80 shadow-sm">
          <CardHeader className="flex items-start justify-between pb-3">
            <div>
              <CardTitle className="text-base font-semibold text-start">خط زمني للانحرافات</CardTitle>
              <CardDescription className="text-sm text-muted-foreground">
                رصد اللحظات الحرجة ومؤشرات الخطر بناءً على z-score والاتجاهات اليومية.
              </CardDescription>
            </div>
            <Badge variant={anomalyCount > 2 ? "destructive" : "secondary"}>{anomalyCount} إشارات</Badge>
          </CardHeader>
          <CardContent>
            <AnomalyTimelineChart data={intelligence.anomalies} />
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-background/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-start">توقعات الأداء</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              مقارنة الأداء الفعلي مقابل التوقعات لثلاثة أيام قادمة.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PredictiveTrendsChart data={intelligence.predictive} />
          </CardContent>
        </Card>
      </div>
    </section>
  );
};

export default Layer3IntelligencePanel;
