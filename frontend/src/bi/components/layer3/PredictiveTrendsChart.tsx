"use client";

import React, { useMemo } from "react";
import type { Layer3Intelligence } from "../../data/intelligence";
import { EChartBase } from "../layer2/EChartBase";

type PredictiveTrendsChartProps = {
  data: Layer3Intelligence["predictive"];
  height?: number;
};

export const PredictiveTrendsChart: React.FC<PredictiveTrendsChartProps> = ({ data, height = 340 }) => {
  const option = useMemo(() => {
    const categories = data.series.flatMap((serie) => serie.points.map((point) => point.timestamp));
    const sortedCategories = Array.from(new Set(categories)).sort();
    const series = data.series.map((serie) => ({
      name: serie.name,
      type: "line",
      smooth: true,
      symbol: "circle",
      symbolSize: serie.kind === "forecast" ? 6 : 8,
      lineStyle: {
        width: serie.kind === "forecast" ? 2 : 3,
        type: serie.kind === "forecast" ? "dashed" : "solid",
      },
      areaStyle: serie.kind === "actual" ? { opacity: 0.15 } : undefined,
      data: sortedCategories.map((timestamp) => {
        const point = serie.points.find((item) => item.timestamp === timestamp);
        return point ? point.value : null;
      }),
    }));
    return {
      tooltip: {
        trigger: "axis",
        valueFormatter: (value: any) => `${Number(value).toFixed(2)} ${data.unit ?? ""}`.trim(),
      },
      legend: {
        top: 0,
      },
      grid: { top: 32, left: 56, right: 24, bottom: 40 },
      xAxis: {
        type: "category",
        data: sortedCategories,
        boundaryGap: false,
        axisLabel: { rotate: sortedCategories.length > 6 ? 30 : 0 },
      },
      yAxis: {
        type: "value",
        name: data.metric,
        splitLine: { lineStyle: { opacity: 0.2 } },
      },
      series,
    };
  }, [data]);

  return <EChartBase option={option} height={height} />;
};

export default PredictiveTrendsChart;
