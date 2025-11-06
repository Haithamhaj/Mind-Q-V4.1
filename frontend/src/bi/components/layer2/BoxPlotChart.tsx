"use client";

import React, { useMemo } from "react";
import type { EChartsCoreOption } from "echarts";
import { EChartBase } from "./EChartBase";
import type { Layer2BoxPlotInsight } from "../../data/insights";

type BoxPlotChartProps = {
  insight: Layer2BoxPlotInsight;
  height?: number;
};

const quantile = (sorted: number[], q: number): number => {
  if (!sorted.length) {
    return 0;
  }
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  if (sorted[base + 1] !== undefined) {
    return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
  }
  return sorted[base];
};

const toBoxStats = (values: number[]): [number, number, number, number, number] => {
  if (!values.length) {
    return [0, 0, 0, 0, 0];
  }
  const sorted = [...values].sort((a, b) => a - b);
  return [
    sorted[0],
    quantile(sorted, 0.25),
    quantile(sorted, 0.5),
    quantile(sorted, 0.75),
    sorted[sorted.length - 1],
  ];
};

export const BoxPlotChart: React.FC<BoxPlotChartProps> = ({ insight, height = 360 }) => {
  const option: EChartsCoreOption = useMemo(() => {
    const stats = insight.dataset.categories.map((category) => {
      const sample = insight.dataset.samples.find((candidate) => candidate.category === category);
      return toBoxStats(sample?.values ?? []);
    });

    const scatterPoints = insight.dataset.samples.flatMap((sample) =>
      sample.values.map((value) => ({
        name: sample.category,
        value,
      })),
    );

    return {
      tooltip: {
        trigger: "item",
        axisPointer: { type: "shadow" },
        backgroundColor: "rgba(15, 23, 42, 0.88)",
        borderRadius: 8,
        formatter: (params: any) => {
          if (Array.isArray(params.value)) {
            const [min, q1, median, q3, max] = params.value;
            return [
              `<strong>${params.name}</strong>`,
              `Min: ${min.toFixed(2)} ${insight.dataset.unit ?? ""}`,
              `Q1: ${q1.toFixed(2)} ${insight.dataset.unit ?? ""}`,
              `Median: ${median.toFixed(2)} ${insight.dataset.unit ?? ""}`,
              `Q3: ${q3.toFixed(2)} ${insight.dataset.unit ?? ""}`,
              `Max: ${max.toFixed(2)} ${insight.dataset.unit ?? ""}`,
            ].join("<br/>");
          }
          return `${params.seriesName}: ${params.value.toFixed(2)} ${insight.dataset.unit ?? ""}`;
        },
      },
      grid: { top: 40, bottom: 40, left: 72, right: 32 },
      xAxis: {
        type: "category",
        data: insight.dataset.categories,
        axisLabel: { interval: 0, rotate: 12 },
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.4)" } },
      },
      yAxis: {
        type: "value",
        name: insight.dataset.unit ?? insight.dataset.label ?? undefined,
        splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.16)" } },
      },
      series: [
        {
          type: "boxplot",
          data: stats,
          itemStyle: {
            color: "rgba(59, 130, 246, 0.3)",
            borderColor: "#3b82f6",
          },
        },
        {
          name: "Raw Samples",
          type: "scatter",
          data: scatterPoints.map((point) => [point.name, point.value]),
          itemStyle: { color: "#22d3ee" },
          symbolSize: 8,
          tooltip: {
            formatter: (params: any) => {
              return `${params.name}: ${params.value[1].toFixed(2)} ${insight.dataset.unit ?? ""}`;
            },
          },
        },
      ],
    };
  }, [insight]);

  return <EChartBase option={option} height={height} />;
};

export default BoxPlotChart;
