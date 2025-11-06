"use client";

import React, { useMemo } from "react";
import type { Layer3Intelligence } from "../../data/intelligence";
import { EChartBase } from "../layer2/EChartBase";

type AnomalyTimelineChartProps = {
  data: Layer3Intelligence["anomalies"];
  height?: number;
};

const severityColor = (severity?: string) => {
  switch (severity) {
    case "critical":
      return "#ef4444";
    case "high":
      return "#f97316";
    default:
      return "#22c55e";
  }
};

export const AnomalyTimelineChart: React.FC<AnomalyTimelineChartProps> = ({ data, height = 320 }) => {
  const option = useMemo(() => {
    const mainSeries = data.series[0] ?? { name: data.metric, points: [] };
    const timestamps = mainSeries.points.map((point) => point.timestamp);
    const values = mainSeries.points.map((point) => point.value);
    const anomalyMarkPoints = data.anomalies.map((anomaly) => {
      const index = timestamps.indexOf(anomaly.timestamp);
      const value = index >= 0 ? values[index] : undefined;
      return {
        coord: [anomaly.timestamp, value ?? 0],
        value: anomaly.score ?? anomaly.label,
        itemStyle: { color: severityColor(anomaly.severity) },
        label: {
          formatter: anomaly.label,
        },
      };
    });

    return {
      tooltip: {
        trigger: "axis",
      },
      grid: { left: 60, right: 24, top: 40, bottom: 40 },
      xAxis: {
        type: "category",
        data: timestamps,
        boundaryGap: false,
      },
      yAxis: {
        type: "value",
        name: data.metric,
        splitLine: { lineStyle: { opacity: 0.2 } },
      },
      series: [
        {
          name: mainSeries.name,
          type: "line",
          smooth: true,
          data: values,
          areaStyle: { opacity: 0.15 },
          lineStyle: { width: 3 },
          symbol: "circle",
          markPoint: {
            data: anomalyMarkPoints,
            symbolSize: 60,
          },
        },
      ],
    };
  }, [data]);

  return <EChartBase option={option} height={height} />;
};

export default AnomalyTimelineChart;
