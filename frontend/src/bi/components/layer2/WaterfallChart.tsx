"use client";

import React, { useMemo } from "react";
import type { EChartsCoreOption } from "echarts";
import { EChartBase } from "./EChartBase";
import type { Layer2WaterfallInsight } from "../../data/insights";

type WaterfallChartProps = {
  insight: Layer2WaterfallInsight;
  height?: number;
};

const formatValue = (value: number, unit?: string) => {
  const rounded = Number.isInteger(value) ? value.toString() : value.toFixed(2);
  return unit ? `${rounded} ${unit}` : rounded;
};

export const WaterfallChart: React.FC<WaterfallChartProps> = ({ insight, height = 360 }) => {
  const option: EChartsCoreOption = useMemo(() => {
    const steps = insight.dataset.steps;
    const categories = steps.map((step) => step.label);
    const assist: number[] = [];
    const increaseSeries: Array<number | { value: number; itemStyle?: Record<string, unknown> }> = [];
    const decreaseSeries: number[] = [];

    let cumulative = 0;
    const totalValue = steps.reduce((acc, step) => {
      if (step.type === "total") {
        return acc;
      }
      return acc + (step.value ?? 0);
    }, 0);

    steps.forEach((step) => {
      if (step.type === "total") {
        assist.push(0);
        increaseSeries.push({
          value: totalValue,
          itemStyle: { color: "#6366f1" },
        });
        decreaseSeries.push(0);
        cumulative = totalValue;
        return;
      }

      const value = step.value ?? 0;
      assist.push(cumulative);

      if (step.type === "baseline") {
        increaseSeries.push({
          value,
          itemStyle: { color: "#94a3b8" },
        });
        decreaseSeries.push(0);
      } else if (value >= 0) {
        increaseSeries.push(value);
        decreaseSeries.push(0);
      } else {
        increaseSeries.push(0);
        decreaseSeries.push(value);
      }

      cumulative += value;
    });

    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: any[]) => {
          const point = params.find((entry) => entry.seriesType === "bar" && entry.seriesName !== "Assist");
          if (!point) {
            return "";
          }
          const step = steps[point.dataIndex];
          const value =
            step.type === "total"
              ? totalValue
              : step.value ?? 0;
          const formatted = formatValue(value, insight.dataset.unit);
          return [`<strong>${step.label}</strong>`, `${formatted}`, step.annotation ? step.annotation : ""]
            .filter(Boolean)
            .join("<br/>");
        },
        backgroundColor: "rgba(15, 23, 42, 0.88)",
        borderRadius: 8,
      },
      grid: { top: 36, bottom: 56, left: 80, right: 32 },
      xAxis: {
        type: "category",
        data: categories,
        axisLabel: { interval: 0, rotate: 16 },
        axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.4)" } },
      },
      yAxis: {
        type: "value",
        name: insight.dataset.unit ?? undefined,
        splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.16)" } },
      },
      series: [
        {
          name: "Assist",
          type: "bar",
          stack: "total",
          itemStyle: {
            borderColor: "transparent",
            color: "transparent",
          },
          emphasis: { disabled: true },
          data: assist,
        },
        {
          name: "Increase",
          type: "bar",
          stack: "total",
          itemStyle: { color: "#22c55e" },
          label: {
            show: true,
            position: "top",
            color: "#0f172a",
            formatter: (params: any) => {
              const value = params.value;
              if (!value || value === 0) {
                return "";
              }
              const step = steps[params.dataIndex];
              const actual = step.type === "total" ? totalValue : value;
              return formatValue(actual, insight.dataset.unit);
            },
          },
          data: increaseSeries,
        },
        {
          name: "Decrease",
          type: "bar",
          stack: "total",
          itemStyle: { color: "#ef4444" },
          label: {
            show: true,
            position: "bottom",
            color: "#991b1b",
            formatter: (params: any) => {
              const value = params.value;
              if (!value || value === 0) {
                return "";
              }
              return formatValue(value, insight.dataset.unit);
            },
          },
          data: decreaseSeries,
        },
      ],
    };
  }, [insight]);

  return <EChartBase option={option} height={height} />;
};

export default WaterfallChart;
