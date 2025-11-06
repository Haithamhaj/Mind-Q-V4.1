"use client";

import React, { useEffect, useMemo, useRef } from "react";

import clsx from "clsx";
import * as echarts from "echarts";
import type { EChartsOption, EChartsType, ECElementEvent } from "echarts";
import { useTheme } from "next-themes";

import { ensureLayer1Theme } from "./ChartTheme";
import type { ChartExportConfig } from "./ChartExport";
import { ChartExport } from "./ChartExport";

export type ChartContainerProps = {
  option: EChartsOption;
  dataset?: Record<string, unknown>[];
  height?: number;
  loading?: boolean;
  emptyMessage?: string;
  className?: string;
  exportConfig?: ChartExportConfig;
  onPointClick?: (row: Record<string, unknown>, event: ECElementEvent) => void;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  dir?: "rtl" | "ltr";
};

const DEFAULT_EMPTY_MESSAGE = "لا توجد بيانات كافية للعَرض حالياً.";

export const ChartContainer: React.FC<ChartContainerProps> = ({
  option,
  dataset,
  height = 320,
  loading = false,
  emptyMessage = DEFAULT_EMPTY_MESSAGE,
  className,
  exportConfig,
  onPointClick,
  title,
  subtitle,
  actions,
  dir = "rtl",
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<EChartsType | null>(null);
  const themeRef = useRef<string | null>(null);
  const { resolvedTheme } = useTheme();

  const rows = useMemo(() => {
    if (dataset) {
      return dataset;
    }
    if (Array.isArray((option.dataset as any)?.source)) {
      return ((option.dataset as any).source ?? []) as Record<string, unknown>[];
    }
    if (Array.isArray(option.dataset)) {
      const first = option.dataset.find((entry) => Array.isArray(entry.source));
      if (first?.source) {
        return first.source as Record<string, unknown>[];
      }
    }
    return [];
  }, [dataset, option.dataset]);

  useEffect(() => {
    const mode = resolvedTheme === "dark" ? "dark" : "light";
    ensureLayer1Theme(mode);
  }, [resolvedTheme]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }

    element.setAttribute("dir", dir);

    const mode = resolvedTheme === "dark" ? "dark" : "light";
    const themeName = `layer1-${mode}`;
    const themeChanged = themeRef.current !== themeName;

    if (!chartRef.current || chartRef.current.isDisposed() || themeChanged) {
      if (chartRef.current && !chartRef.current.isDisposed()) {
        chartRef.current.dispose();
      }
      chartRef.current = echarts.init(element, themeName, { renderer: "svg" });
      themeRef.current = themeName;
    }

    const chart = chartRef.current;
    chart.setOption(option, { notMerge: true, lazyUpdate: false });
    chart.resize();

    if (onPointClick) {
      chart.off("click");
      chart.on("click", (event: ECElementEvent) => {
        if (!onPointClick) {
          return;
        }
        const dataIndex = typeof event.dataIndex === "number" ? event.dataIndex : undefined;
        const row = (dataIndex !== undefined && rows[dataIndex]) || (event.data as Record<string, unknown>);
        if (row && typeof row === "object") {
          onPointClick(row as Record<string, unknown>, event);
        }
      });
    }

    const handleResize = () => {
      chart.resize();
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [option, resolvedTheme, dir, onPointClick, rows]);

  useEffect(() => {
    return () => {
      if (chartRef.current && !chartRef.current.isDisposed()) {
        chartRef.current.dispose();
      }
      chartRef.current = null;
    };
  }, []);

  if (loading) {
    return (
      <div
        className={clsx(
          "h-[280px] w-full animate-pulse rounded-2xl border border-border/40 bg-muted/40 shadow-sm",
          className,
        )}
      />
    );
  }

  if (!rows?.length) {
    return (
      <div
        className={clsx(
          "flex h-full min-h-[200px] w-full items-center justify-center rounded-2xl border border-dashed border-border/60 bg-muted/20 p-6 text-sm text-muted-foreground shadow-sm",
          className,
        )}
      >
        {emptyMessage}
      </div>
    );
  }

  const resolvedExport: ChartExportConfig | undefined =
    exportConfig && exportConfig.columns.length
      ? {
          ...exportConfig,
          rows: exportConfig.rows ?? rows,
        }
      : undefined;

  return (
    <div
      className={clsx(
        "relative flex w-full flex-col gap-3 rounded-2xl border border-border/60 bg-background/70 p-4 shadow-sm backdrop-blur",
        className,
      )}
    >
      {(title || resolvedExport || actions || subtitle) && (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            {title ? <h3 className="text-sm font-semibold text-foreground">{title}</h3> : null}
            {subtitle ? <p className="text-xs text-muted-foreground">{subtitle}</p> : null}
          </div>
          <div className="flex items-center gap-2">
            {actions}
            {resolvedExport ? <ChartExport {...resolvedExport} /> : null}
          </div>
        </div>
      )}
      <div className="relative w-full" style={{ height }}>
        <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      </div>
    </div>
  );
};

export default ChartContainer;
