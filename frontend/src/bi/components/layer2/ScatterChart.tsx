"use client";

import React, { useMemo } from "react";
import type { EChartsCoreOption } from "echarts";
import { EChartBase } from "./EChartBase";
import type { Layer2ScatterInsight } from "../../data/insights";

type ScatterChartProps = {
  insight: Layer2ScatterInsight;
  height?: number;
};

export const ScatterChart: React.FC<ScatterChartProps> = ({ insight, height = 360 }) => {
  const option: EChartsCoreOption = useMemo(() => {
    const colorPalette = ["#38bdf8", "#f97316", "#22c55e", "#6366f1", "#ec4899", "#facc15", "#0ea5e9"];
    const categoryMap = new Map<string, number>();

    const series = insight.dataset.points.reduce<Record<string, { data: Array<[number, number, number?, string?]>; color: string }>>(
      (acc, point) => {
        const category = point.category ?? "Unassigned";
        if (!acc[category]) {
          const index = categoryMap.size;
          categoryMap.set(category, index);
          acc[category] = {
            data: [],
            color: colorPalette[index % colorPalette.length],
          };
        }
        acc[category].data.push([point.x, point.y, point.size ?? 16, point.label ?? point.id]);
        return acc;
      },
      {},
    );

    return {
      tooltip: {
        trigger: "item",
        borderRadius: 8,
        backgroundColor: "rgba(15, 23, 42, 0.88)",
        formatter: (params: any) => {
          const [x, y, size, label] = params.value;
          const sizeLabel = insight.dataset.axisLabels?.size ?? insight.dataset.sizeKey ?? "Size";
          return [
            `<strong>${label}</strong>`,
            `${insight.dataset.axisLabels?.x ?? insight.dataset.xKey}: ${x.toFixed(1)}`,
            `${insight.dataset.axisLabels?.y ?? insight.dataset.yKey}: ${y.toFixed(1)}`,
            `${sizeLabel}: ${size?.toFixed ? size.toFixed(0) : size}`,
          ].join("<br/>");
        },
      },
      legend: {
        top: 0,
        textStyle: { color: "rgba(148, 163, 184, 0.9)" },
      },
      grid: { top: 48, bottom: 60, left: 80, right: 32 },
      xAxis: {
        name: insight.dataset.axisLabels?.x ?? insight.dataset.xKey,
        type: "value",
        nameLocation: "middle",
        nameGap: 28,
        splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.12)" } },
      },
      yAxis: {
        name: insight.dataset.axisLabels?.y ?? insight.dataset.yKey,
        type: "value",
        splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.12)" } },
      },
      series: Object.entries(series).map(([category, meta]) => ({
        name: category,
        type: "scatter",
        data: meta.data,
        symbolSize: (value: any[]) => {
          const raw = value[2] ?? 16;
          return Math.max(Math.sqrt(raw), 8);
        },
        itemStyle: { color: meta.color },
      })),
    };
  }, [insight]);

  return <EChartBase option={option} height={height} />;
};

export default ScatterChart;
