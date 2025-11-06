"use client";

import React, { useMemo, useCallback } from "react";
import clsx from "clsx";
import type { EChartsCoreOption, SeriesOption } from "echarts";
import type { EChartsType } from "echarts";
import { EChartBase } from "../components/layer2/EChartBase";

const DEFAULT_COLORS = ["#1d4ed8", "#9333ea", "#0ea5e9", "#16a34a", "#f97316", "#f43f5e", "#10b981"];

type ChartType = "line" | "bar" | "area" | "funnel" | "treemap" | "combo";

type ChartContainerProps = {
  type: ChartType;
  data: Record<string, unknown>[];
  x: string;
  y: string | string[];
  secondaryY?: string | string[];
  height?: number;
  palette?: string[];
  loading?: boolean;
  emptyMessage?: string;
  onPointClick?: (payload: Record<string, unknown>) => void;
  debugId?: string;
};

const ensureArray = (value: string | string[] | undefined): string[] => {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
};

const EmptyState = ({ message }: { message: string }) => (
  <div className="flex h-full w-full items-center justify-center rounded-2xl border border-dashed border-border/60 bg-muted/30 p-6 text-sm text-muted-foreground">
    {message}
  </div>
);

export const ChartContainer: React.FC<ChartContainerProps> = ({
  type,
  data,
  x,
  y,
  secondaryY,
  height = 280,
  palette = DEFAULT_COLORS,
  loading = false,
  emptyMessage = "لا توجد بيانات لعرض المخطط.",
  onPointClick,
  debugId = "unknown",
}) => {
  const primary = ensureArray(y);
  const secondarySeries = ensureArray(secondaryY);
  const safeData = useMemo(() => (Array.isArray(data) ? data : []), [data]);

  const categories = useMemo(() => safeData.map((d) => String((d as any)[x])), [safeData, x]);

  const buildSeries = useCallback((): SeriesOption[] => {
    if (type === "funnel") {
      const key = primary[0];
      return [
        {
          type: "funnel",
          data: safeData.map((row, idx) => ({
            name: String((row as any)[x]),
            value: Number((row as any)[key] ?? 0),
            __row: row,
            itemStyle: { color: palette[idx % palette.length] },
          })),
        },
      ];
    }
    if (type === "treemap") {
      const key = primary[0];
      return [
        {
          type: "treemap",
          roam: false,
          data: safeData.map((row, idx) => ({
            name: String((row as any)[x]),
            value: Number((row as any)[key] ?? 0),
            __row: row,
            itemStyle: { color: palette[idx % palette.length] },
          })),
        },
      ];
    }

    const primarySeries: SeriesOption[] = primary.map((key, idx) => ({
      type: type === "area" ? "line" : (type as any),
      smooth: type === "line" || type === "area",
      areaStyle: type === "area" ? {} : undefined,
      name: key,
      data: safeData.map((row) => ({ value: Number((row as any)[key] ?? 0), ...row })),
      itemStyle: { color: palette[idx % palette.length] },
    }));

    const secondaries: SeriesOption[] = secondarySeries.map((key, idx) => ({
      type: "line",
      yAxisIndex: 1,
      smooth: true,
      name: key,
      data: safeData.map((row) => ({ value: Number((row as any)[key] ?? 0), ...row })),
      itemStyle: { color: palette[(primary.length + idx) % palette.length] },
    }));

    return [...primarySeries, ...secondaries];
  }, [type, primary, secondarySeries, safeData, x, palette]);

  const option: EChartsCoreOption = useMemo(
    () => ({
      tooltip: { trigger: type === "funnel" || type === "treemap" ? "item" : "axis" },
      grid: { top: 24, right: secondarySeries.length ? 48 : 16, bottom: 40, left: 40 },
      xAxis: type === "funnel" || type === "treemap" ? undefined : { type: "category", data: categories },
      yAxis:
        type === "funnel" || type === "treemap"
          ? undefined
          : [
              { type: "value" },
              ...(secondarySeries.length ? [{ type: "value" }] : []),
            ],
      legend: { top: 0 },
      series: buildSeries(),
    }),
    [type, categories, buildSeries, secondarySeries.length],
  );

  const handleReady = useCallback((instance: EChartsType) => {
    if (!onPointClick) return;
    instance.off("click");
    instance.on("click", (params: any) => {
      const payload = params?.data?.__row ?? params?.data;
      if (payload) onPointClick(payload as any);
    });
  }, [onPointClick]);

  if (loading) {
    return (
      <div className="h-[280px] w-full animate-pulse rounded-2xl border border-border/30 bg-muted/50" aria-hidden="true" />
    );
  }

  if (!safeData.length || !primary.length) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <div
      className={clsx("relative flex w-full flex-col gap-2 rounded-2xl border border-border/60 bg-background/70 p-4 shadow-sm")}
      dir="rtl"
    >
      <EChartBase option={option} height={height} onReady={handleReady} />
    </div>
  );
};

export default ChartContainer;
