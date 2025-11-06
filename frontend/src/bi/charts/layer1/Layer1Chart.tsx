"use client";

import React, { useMemo } from "react";

import type { EChartsOption } from "echarts";

import { ChartContainer } from "../shared/ChartContainer";
import type { ChartExportConfig, ChartExportColumn } from "../shared/ChartExport";
import { buildBilingualLabel, resolveFieldLabel } from "../shared/labels";
import { layer1Palette } from "../shared/ChartTheme";

const ensureArray = (value: string | string[] | undefined): string[] => {
  if (!value) {
    return [];
  }
  return Array.isArray(value) ? value : [value];
};

export type Layer1ChartType = "line" | "bar" | "area" | "funnel" | "treemap" | "combo" | "pie";

export type Layer1ChartProps = {
  type: Layer1ChartType;
  data: Record<string, unknown>[];
  x: string;
  y: string | string[];
  secondaryY?: string | string[];
  height?: number;
  palette?: string[];
  loading?: boolean;
  emptyMessage?: string;
  debugId?: string;
  exportConfig?: ChartExportConfig;
  onPointClick?: (payload: Record<string, unknown>) => void;
};

const buildExportColumns = (x: string, primary: string[], secondary: string[]): ChartExportColumn[] => {
  const columns = new Map<string, ChartExportColumn>();
  const register = (key: string | undefined) => {
    if (!key || columns.has(key)) {
      return;
    }
    const { en, ar } = resolveFieldLabel(key);
    columns.set(key, { key, label: en, labelAr: ar });
  };

  register(x);
  primary.forEach(register);
  secondary.forEach(register);

  return Array.from(columns.values());
};

const buildAxisLineOption = () => ({
  lineStyle: {
    color: "rgba(148, 163, 184, 0.35)",
  },
});

const buildGrid = () => ({
  left: 48,
  right: 40,
  top: 56,
  bottom: 56,
});

export const Layer1Chart: React.FC<Layer1ChartProps> = ({
  type,
  data,
  x,
  y,
  secondaryY,
  height = 280,
  palette = layer1Palette,
  loading = false,
  emptyMessage,
  debugId,
  exportConfig,
  onPointClick,
}) => {
  const primarySeries = ensureArray(y);
  const secondarySeries = ensureArray(secondaryY);

  const { option, finalExportConfig } = useMemo(() => {
    const exportColumns = exportConfig?.columns ?? buildExportColumns(x, primarySeries, secondarySeries);
    const resolvedExport: ChartExportConfig | undefined = exportConfig
      ? { ...exportConfig, columns: exportConfig.columns ?? exportColumns, rows: exportConfig.rows ?? data }
      : {
          fileName: debugId ?? "layer1-chart",
          columns: exportColumns,
          rows: data,
        };

    const baseOption: EChartsOption = {
      color: palette,
      dataset: { source: data },
      grid: buildGrid(),
      legend: {
        top: 8,
        data: [...primarySeries, ...secondarySeries].map((key) => buildBilingualLabel(key)),
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        borderRadius: 8,
        padding: 12,
      },
      xAxis: {
        type: "category",
        name: buildBilingualLabel(x),
        nameGap: 24,
        nameLocation: "middle",
        axisLine: buildAxisLineOption(),
        axisLabel: { fontSize: 11 },
      },
      yAxis: [
        {
          type: "value",
          axisLabel: { fontSize: 11 },
          axisLine: buildAxisLineOption(),
          splitLine: {
            lineStyle: {
              color: "rgba(148, 163, 184, 0.22)",
            },
          },
        },
      ],
      series: [],
    };

    const lineSeries = (key: string, index: number, opts?: { area?: boolean; yAxisIndex?: number }) => ({
      type: "line" as const,
      name: buildBilingualLabel(key),
      encode: { x, y: key },
      symbol: "circle",
      symbolSize: 6,
      smooth: true,
      showSymbol: false,
      lineStyle: {
        width: 3,
      },
      areaStyle: opts?.area ? { opacity: 0.15 } : undefined,
      yAxisIndex: opts?.yAxisIndex ?? 0,
      emphasis: { focus: "series" },
      itemStyle: {
        color: palette[index % palette.length],
      },
    });

    const barSeries = (key: string, index: number) => ({
      type: "bar" as const,
      name: buildBilingualLabel(key),
      encode: { x, y: key },
      barMaxWidth: 42,
      emphasis: { focus: "series" },
      itemStyle: {
        color: palette[index % palette.length],
        borderRadius: [8, 8, 0, 0],
      },
    });

    let option: EChartsOption = baseOption;

    if (type === "line" || type === "area") {
      option = {
        ...baseOption,
        tooltip: {
          ...baseOption.tooltip,
          trigger: "axis",
          axisPointer: { type: "line" },
        },
        series: primarySeries.map((key, index) => lineSeries(key, index, { area: type === "area" })),
      };
    } else if (type === "bar") {
      option = {
        ...baseOption,
        series: primarySeries.map((key, index) => barSeries(key, index)),
      };
    } else if (type === "combo") {
      const valueAxis = baseOption.yAxis as any[];
      if (secondarySeries.length) {
        valueAxis.push({
          type: "value",
          axisLabel: {
            fontSize: 11,
            formatter: "{value}%",
          },
          splitLine: { show: false },
        });
      }
      option = {
        ...baseOption,
        yAxis: valueAxis,
        series: [
          ...primarySeries.map((key, index) => barSeries(key, index)),
          ...secondarySeries.map((key, index) =>
            lineSeries(key, index + primarySeries.length, { yAxisIndex: 1 }),
          ),
        ],
      };
    } else if (type === "funnel") {
      option = {
        ...baseOption,
        tooltip: {
          trigger: "item",
          borderRadius: 8,
          padding: 12,
        },
        legend: {
          ...baseOption.legend,
          orient: "vertical",
          right: 0,
        },
        series: [
          {
            type: "funnel",
            name: buildBilingualLabel(primarySeries[0]),
            encode: { itemName: x, value: primarySeries[0] },
            label: {
              show: true,
              formatter: "{b}: {c}",
            },
            emphasis: { focus: "self" },
            itemStyle: {
              borderColor: "rgba(15, 23, 42, 0.5)",
            },
          },
        ],
      };
    } else if (type === "treemap") {
      option = {
        ...baseOption,
        tooltip: {
          trigger: "item",
          borderRadius: 8,
          padding: 12,
        },
        legend: undefined,
        series: [
          {
            type: "treemap",
            data: data.map((row) => ({
              name: String(row[x] ?? ""),
              value: Number(row[primarySeries[0]]) || 0,
            })),
            roam: false,
            label: {
              show: true,
              formatter: "{b}\n{c}",
            },
            breadcrumb: { show: false },
          },
        ],
      };
    } else if (type === "pie") {
      option = {
        ...baseOption,
        dataset: undefined,
        legend: {
          ...baseOption.legend,
          orient: "vertical",
          right: 0,
          top: "middle",
        },
        tooltip: {
          trigger: "item",
          formatter: "{b}: {c} ({d}%)",
        },
        series: [
          {
            type: "pie",
            radius: ["38%", "70%"],
            center: ["40%", "50%"],
            data: data.map((row, index) => ({
              name: String(row[x] ?? ""),
              value: Number(row[primarySeries[0]]) || 0,
              itemStyle: { color: palette[index % palette.length] },
            })),
            label: { formatter: "{b}\n{d}%" },
          },
        ],
      };
    } else {
      option = {
        ...baseOption,
        series: primarySeries.map((key, index) => barSeries(key, index)),
      };
    }

    return {
      option,
      finalExportConfig: resolvedExport,
    };
  }, [type, data, x, primarySeries, secondarySeries, palette, debugId, exportConfig]);

  return (
    <ChartContainer
      option={option}
      dataset={data}
      height={height}
      loading={loading}
      emptyMessage={emptyMessage}
      exportConfig={finalExportConfig}
      dir="rtl"
      onPointClick={
        onPointClick
          ? (row) => {
              onPointClick(row);
            }
          : undefined
      }
    />
  );
};

export default Layer1Chart;
