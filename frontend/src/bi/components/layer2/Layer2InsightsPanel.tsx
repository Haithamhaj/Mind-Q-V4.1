"use client";

import React from "react";
import clsx from "clsx";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { HeatmapChart } from "./HeatmapChart";
import { BoxPlotChart } from "./BoxPlotChart";
import { WaterfallChart } from "./WaterfallChart";
import { ScatterChart } from "./ScatterChart";
import { MultiAxisLineChart } from "./MultiAxisLineChart";
import {
  layer2Insights,
  type Layer2Insight,
  type Layer2HeatmapInsight,
  type Layer2BoxPlotInsight,
  type Layer2WaterfallInsight,
  type Layer2ScatterInsight,
  type Layer2MultiAxisLineInsight,
} from "../../data/insights";

type Layer2InsightsPanelProps = {
  insights?: Layer2Insight[];
  className?: string;
};

const MetricsSummary: React.FC<{ insight: Layer2Insight }> = ({ insight }) => {
  if (!insight.metrics) {
    return null;
  }

  const { current, baseline, delta, deltaPct, unit } = insight.metrics;

  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
      <span className="rounded-lg bg-muted px-2 py-1 font-semibold text-foreground/90">
        {current.toFixed(2)} {unit ?? ""}
      </span>
      {baseline !== undefined && (
        <span>
          Baseline:{" "}
          <span className="font-medium text-foreground/80">
            {baseline.toFixed(2)} {unit ?? ""}
          </span>
        </span>
      )}
      {delta !== undefined && (
        <span className={delta >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}>
          Δ {delta >= 0 ? "+" : ""}
          {delta.toFixed(2)} {unit ?? ""}
        </span>
      )}
      {deltaPct !== undefined && (
        <span className={deltaPct >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"}>
          ({deltaPct >= 0 ? "+" : ""}
          {(deltaPct * 100).toFixed(1)}%)
        </span>
      )}
    </div>
  );
};

const renderChart = (insight: Layer2Insight) => {
  switch (insight.chartType) {
    case "heatmap":
      return <HeatmapChart insight={insight as Layer2HeatmapInsight} />;
    case "boxplot":
      return <BoxPlotChart insight={insight as Layer2BoxPlotInsight} />;
    case "waterfall":
      return <WaterfallChart insight={insight as Layer2WaterfallInsight} />;
    case "scatter":
      return <ScatterChart insight={insight as Layer2ScatterInsight} />;
    case "multiAxisLine":
      return <MultiAxisLineChart insight={insight as Layer2MultiAxisLineInsight} />;
    default:
      return null;
  }
};

export const Layer2InsightsPanel: React.FC<Layer2InsightsPanelProps> = ({
  insights: collection = layer2Insights,
  className,
}) => {
  return (
    <section className={clsx("flex flex-col gap-6 rounded-2xl border border-border/60 bg-background/70 p-4 shadow-sm", className)}>
      <header className="mb-6 flex flex-col gap-2 text-start">
        <h2 className="text-xl font-semibold text-foreground">تحليلات الطبقة الثانية</h2>
        <p className="text-sm text-muted-foreground">
          مكونات مرئية متقدمة تعتمد على ECharts لاستكشاف الانحرافات، التشتت، والتوجهات متعددة المحاور داخل بيانات COD.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {collection.map((insight) => (
          <Card key={insight.id} className="flex flex-col gap-3 border-border/60 bg-background/70 shadow-sm">
            <CardHeader className="space-y-2 text-start">
              <CardTitle className="flex items-center justify-between gap-3">
                <span>{insight.title}</span>
                {insight.confidence && (
                  <Badge variant="outline" className="capitalize">
                    {insight.confidence} confidence
                  </Badge>
                )}
              </CardTitle>
              <CardDescription className="text-sm text-muted-foreground">{insight.summary}</CardDescription>
              <MetricsSummary insight={insight} />
              {insight.filters && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {Object.entries(insight.filters).map(([dimension, values]) => (
                    <Badge key={dimension} variant="secondary" className="text-[11px] font-medium">
                      {dimension}: {values.join(" • ")}
                    </Badge>
                  ))}
                </div>
              )}
            </CardHeader>
            <CardContent className="flex-1">
              {renderChart(insight) ?? (
                <div className="rounded-2xl border border-dashed border-border/60 p-8 text-sm text-muted-foreground">
                  لا توجد بيانات لعرض هذا الرسم حالياً.
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
};

export default Layer2InsightsPanel;
