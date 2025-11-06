"use client";

import React, { useMemo } from "react";
import type { EChartsCoreOption } from "echarts";
import { EChartBase } from "./EChartBase";
import type { Layer2MultiAxisLineInsight } from "../../data/insights";

type MultiAxisLineChartProps = {
  insight: Layer2MultiAxisLineInsight;
  height?: number;
};

export const MultiAxisLineChart: React.FC<MultiAxisLineChartProps> = ({ insight, height = 360 }) => {
  const option: EChartsCoreOption = useMemo(() => {
    const palette = ["#2563eb", "#f97316", "#10b981", "#ec4899", "#facc15", "#0ea5e9", "#8b5cf6"];

    const leftSeries = insight.dataset.leftYAxis.series.map((series, index) => ({
      name: series.name,
      type: "line",
      yAxisIndex: 0,
      smooth: true,
      symbol: "circle",
      symbolSize: 8,
      lineStyle: { width: 3, color: palette[index % palette.length] },
      itemStyle: { color: palette[index % palette.length] },
      data: series.data,
    }));

    const rightSeries = insight.dataset.rightYAxis
      ? insight.dataset.rightYAxis.series.map((series, index) => {
          const paletteIndex = (insight.dataset.leftYAxis.series.length + index) % palette.length;
          return {
            name: series.name,
            type: "line",
            yAxisIndex: 1,
            smooth: true,
            symbol: "diamond",
            symbolSize: 8,
            lineStyle: { width: 2, type: "dashed", color: palette[paletteIndex] },
            itemStyle: { color: palette[paletteIndex] },
            data: series.data,
          };
        })
      : [];

    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        backgroundColor: "rgba(15, 23, 42, 0.88)",
        borderRadius: 8,
      },
      legend: {
        top: 0,
        textStyle: { color: "rgba(148, 163, 184, 0.9)" },
        icon: "roundRect",
      },
      grid: { top: 48, bottom: 60, left: 64, right: 64 },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: insight.dataset.xAxis,
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.35)" } },
      },
      yAxis: [
        {
          type: "value",
          name: insight.dataset.leftYAxis.label ?? undefined,
          axisLine: { lineStyle: { color: "rgba(59, 130, 246, 0.5)" } },
          splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.14)" } },
        },
        insight.dataset.rightYAxis
          ? {
              type: "value",
              name: insight.dataset.rightYAxis.label ?? undefined,
              axisLine: { lineStyle: { color: "rgba(236, 72, 153, 0.5)" } },
              splitLine: { show: false },
            }
          : undefined,
      ].filter(Boolean) as EChartsCoreOption["yAxis"],
      series: [...leftSeries, ...rightSeries],
    };
  }, [insight]);

  return <EChartBase option={option} height={height} />;
};

export default MultiAxisLineChart;
