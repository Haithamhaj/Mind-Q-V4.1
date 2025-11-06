"use client";

import React, { useMemo } from "react";
import type { EChartsCoreOption } from "echarts";
import { EChartBase } from "./EChartBase";
import type { Layer2HeatmapInsight } from "../../data/insights";

type HeatmapChartProps = {
  insight: Layer2HeatmapInsight;
  height?: number;
};

export const HeatmapChart: React.FC<HeatmapChartProps> = ({ insight, height = 360 }) => {
  const option: EChartsCoreOption = useMemo(() => {
    const values = insight.dataset.cells.map((cell) => cell.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const xIndex = new Map(insight.dataset.xAxis.map((label, index) => [label, index]));
    const yIndex = new Map(insight.dataset.yAxis.map((label, index) => [label, index]));

    return {
      tooltip: {
        position: "top",
        formatter: (params: any) => {
          const value = params.value?.[2] ?? params.value;
          const formatted = typeof value === "number" ? value.toFixed(1) : value;
          return [
            `<strong>${params.name}</strong>`,
            `${insight.dataset.xLabel ?? "X"}: ${params.axisValueLabel}`,
            `${insight.dataset.yLabel ?? "Y"}: ${params.seriesName}`,
            `${insight.dataset.colorLabel ?? "Value"}: ${formatted}`,
          ].join("<br/>");
        },
        borderRadius: 8,
        backgroundColor: "rgba(15, 23, 42, 0.88)",
      },
      grid: {
        top: 48,
        bottom: 72,
        left: 100,
        right: 24,
      },
      xAxis: {
        type: "category",
        data: insight.dataset.xAxis,
        name: insight.dataset.xLabel,
        axisLabel: { interval: 0, rotate: 18 },
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.4)" } },
      },
      yAxis: {
        type: "category",
        data: insight.dataset.yAxis,
        name: insight.dataset.yLabel,
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.4)" } },
      },
      visualMap: {
        min,
        max,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 16,
        text: ["High", "Low"],
        inRange: {
          color: ["#0f172a", "#2563eb", "#38bdf8", "#fbbf24"],
        },
      },
      series: [
        {
          name: insight.dataset.yLabel ?? "Segment",
          type: "heatmap",
          data: insight.dataset.cells.map((cell) => [
            xIndex.get(cell.x) ?? 0,
            yIndex.get(cell.y) ?? 0,
            cell.value,
          ]),
          label: {
            show: true,
            color: "#f1f5f9",
            formatter: ({ value }: any) => {
              const raw = value?.[2] ?? value;
              return typeof raw === "number" ? raw.toFixed(1) : raw;
            },
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 12,
              shadowColor: "rgba(30, 64, 175, 0.35)",
            },
          },
        },
      ],
    };
  }, [insight]);

  return <EChartBase option={option} height={height} />;
};

export default HeatmapChart;
