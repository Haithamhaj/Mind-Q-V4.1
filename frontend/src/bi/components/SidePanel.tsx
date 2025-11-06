"use client";

import React, { useEffect, useMemo, useState } from "react";
import clsx from "clsx";

import ChartContainer from "./ChartContainer";
import { useBiData, useFilteredDataset } from "../data";
import type { MetricSpec } from "../data";

type SidePanelProps = {
  kpiId?: string | null;
  open: boolean;
  onClose: () => void;
  dimension?: string;
  onDimensionChange?: (dimension: string) => void;
};

type AggregatedPoint = {
  label: string;
  value: number;
  secondary?: number;
};

const parseFormula = (formula?: string): { aggregator: string; column: string | null } => {
  if (!formula) {
    return { aggregator: "SUM", column: null };
  }
  const trimmed = formula.trim();
  const match = trimmed.match(/([\w]+)\s*\(\s*([^)]+)\s*\)/i);
  if (!match) {
    return { aggregator: "SUM", column: trimmed };
  }
  return { aggregator: match[1].toUpperCase(), column: match[2] };
};

const aggregateValue = (values: number[], aggregator: string) => {
  switch (aggregator) {
    case "AVG":
    case "MEAN":
      return values.length ? values.reduce((acc, val) => acc + val, 0) / values.length : 0;
    case "MAX":
      return Math.max(...values);
    case "MIN":
      return Math.min(...values);
    default:
      return values.reduce((acc, val) => acc + val, 0);
  }
};

const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;

export const SidePanel: React.FC<SidePanelProps> = ({ kpiId, open, onClose, dimension, onDimensionChange }) => {
  const { metrics, dimensions, catalogMeta } = useBiData();
  const dataset = useFilteredDataset();
  const metric: MetricSpec | undefined = metrics.find((item) => item.id === kpiId);
  const categoricalDims = dimensions.categorical ?? [];
  const defaultDimension = categoricalDims[0]?.name;
  const [localDimension, setLocalDimension] = useState<string | undefined>(dimension ?? defaultDimension);
  const normalizedKpiId = useMemo(() => {
    if (!kpiId) return null;
    return kpiId.startsWith("kpi_") ? kpiId.slice(4) : kpiId;
  }, [kpiId]);
  const catalogEntry = useMemo(() => {
    if (!normalizedKpiId) {
      return null;
    }
    const entries = catalogMeta.kpiCatalog?.kpis ?? [];
    return entries.find((entry) => entry.name === normalizedKpiId) ?? null;
  }, [catalogMeta.kpiCatalog, normalizedKpiId]);

  useEffect(() => {
    setLocalDimension(dimension ?? defaultDimension);
  }, [dimension, defaultDimension]);

  const activeDimension = dimension ?? localDimension;

  const { aggregator, column } = parseFormula(metric?.formula);
  const timeColumn = metric?.time_col ?? dimensions.date[0]?.name ?? null;

  const numericValues = useMemo(() => {
    if (!column) return [];
    return dataset
      .map((row) => {
        const raw = row[column];
        const value = Number(raw);
        return Number.isFinite(value) ? value : null;
      })
      .filter((value): value is number => value !== null);
  }, [dataset, column]);

  const latestValue = numericValues.at(-1) ?? null;

  const trendData = useMemo<AggregatedPoint[]>(() => {
    if (!column || !timeColumn) return [];
    const groups = new Map<string, number[]>();
    dataset.forEach((row) => {
      const rawValue = Number(row[column]);
      const rawTs = row[timeColumn];
      if (!Number.isFinite(rawValue) || rawTs === undefined || rawTs === null) {
        return;
      }
      const key = String(rawTs);
      groups.set(key, [...(groups.get(key) ?? []), rawValue]);
    });
    return Array.from(groups.entries())
      .map(([label, values]) => ({
        label,
        value: aggregateValue(values, aggregator),
      }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [dataset, column, timeColumn, aggregator]);

  const breakdownData = useMemo<AggregatedPoint[]>(() => {
    if (!column || !activeDimension) return [];
    const groups = new Map<string, number[]>();
    dataset.forEach((row) => {
      const rawValue = Number(row[column]);
      const rawDim = row[activeDimension];
      if (!Number.isFinite(rawValue) || rawDim === undefined || rawDim === null) return;
      const key = String(rawDim);
      groups.set(key, [...(groups.get(key) ?? []), rawValue]);
    });
    const entries = Array.from(groups.entries()).map(([label, values]) => ({
      label,
      value: aggregateValue(values, aggregator),
    }));
    const total = entries.reduce((acc, entry) => acc + entry.value, 0);
    return entries
      .map((entry) => ({
        ...entry,
        secondary: total ? entry.value / total : 0,
      }))
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  }, [dataset, column, activeDimension, aggregator]);

  const total = breakdownData.reduce((acc, entry) => acc + entry.value, 0);
  const hasTimeSeries = Boolean(timeColumn && trendData.length);
  const hasBreakdown = Boolean(activeDimension && breakdownData.length);

  const handleDimensionChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value;
    setLocalDimension(value);
    onDimensionChange?.(value);
  };

  if (!open) {
    return null;
  }

  return (
    <aside
      dir="rtl"
      className={clsx(
        "fixed inset-y-0 end-0 z-40 w-full max-w-xl transform bg-background/95 p-6 shadow-2xl backdrop-blur transition-transform duration-300",
        open ? "translate-x-0" : "translate-x-full",
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs text-muted-foreground">???? ????</span>
          <h2 className="text-2xl font-semibold tracking-tight">{metric?.title ?? kpiId ?? "KPI"}</h2>
          {latestValue !== null && <p className="text-sm text-muted-foreground">??? ????: {latestValue.toLocaleString()}</p>}
          {catalogEntry && (
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-muted-foreground">
              {catalogEntry.owner && (
                <div>
                  <dt className="font-medium text-foreground">??????</dt>
                  <dd className="truncate">{catalogEntry.owner}</dd>
                </div>
              )}
              {catalogEntry.visibility && (
                <div>
                  <dt className="font-medium text-foreground">???? ???????</dt>
                  <dd className="capitalize">{catalogEntry.visibility}</dd>
                </div>
              )}
              {catalogEntry.business_goal && (
                <div className="col-span-2">
                  <dt className="font-medium text-foreground">?????? ??????</dt>
                  <dd className="line-clamp-2">{catalogEntry.business_goal}</dd>
                </div>
              )}
              {catalogEntry.ml_usage && (
                <div className="col-span-2">
                  <dt className="font-medium text-foreground">?????? ???? ????????</dt>
                  <dd className="line-clamp-2">{catalogEntry.ml_usage}</dd>
                </div>
              )}
            </dl>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full border border-border px-3 py-1 text-sm font-medium text-muted-foreground transition hover:bg-muted/50"
        >
          ?????
        </button>
      </div>
      <section className="mt-6 space-y-4">
        <header className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-muted-foreground">الاتجاه الزمني</h3>
        </header>
        {hasTimeSeries ? (
          <ChartContainer
            type="area"
            data={trendData.map((item) => ({
              [timeColumn ?? "period"]: item.label,
              value: item.value,
            }))}
            x={timeColumn ?? "period"}
            y="value"
            height={220}
            emptyMessage="لا توجد بيانات زمنية متاحة."
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
            لا يوجد عمود زمني مرتبط بهذا المؤشر. يعرض القسم التالي التوزيع حسب الأبعاد المتاحة.
          </div>
        )}
      </section>

      <section className="mt-6 space-y-4">
        <header className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-muted-foreground">التقسيم حسب الأبعاد</h3>
          {categoricalDims.length > 0 && (
            <select
              value={activeDimension}
              onChange={handleDimensionChange}
              className="rounded-xl border border-border bg-background px-3 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-primary/50"
            >
              {categoricalDims.map((dim) => (
                <option key={dim.name} value={dim.name}>
                  {dim.name}
                </option>
              ))}
            </select>
          )}
        </header>
        {hasBreakdown ? (
          <ChartContainer
            type="bar"
            data={breakdownData.map((item) => ({
              [activeDimension ?? "dimension"]: item.label,
              value: item.value,
              share: item.secondary,
            }))}
            x={activeDimension ?? "dimension"}
            y="value"
            secondaryY={hasTimeSeries ? "share" : undefined}
            height={260}
            emptyMessage="لا توجد بيانات للتقسيم."
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
            لا توجد أبعاد تصنيفية متاحة لحساب المساهمين الأعلى.
          </div>
        )}
      </section>

      <section className="mt-6 space-y-3">
        <header className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-muted-foreground">أعلى المساهمين</h3>
          <span className="text-xs text-muted-foreground">الإجمالي: {total.toLocaleString()}</span>
        </header>
        <div className="space-y-2">
          {breakdownData.slice(0, 5).map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between rounded-xl border border-border/50 bg-muted/30 px-3 py-2 text-sm"
            >
              <span className="truncate font-medium">{item.label}</span>
              <div className="flex items-center gap-3">
                <span className="text-muted-foreground">{item.value.toLocaleString()}</span>
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">
                  {item.secondary !== undefined ? formatPercent(item.secondary) : "—"}
                </span>
              </div>
            </div>
          ))}
          {!breakdownData.length && <span className="text-sm text-muted-foreground">لم يتم العثور على مساهمين.</span>}
        </div>
      </section>

      {catalogEntry && (
        <section className="mt-6 space-y-3">
          <header className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-muted-foreground">????? ????????</h3>
            {catalogEntry.freshness_sla_hours && (
              <span className="text-xs text-muted-foreground">SLA {catalogEntry.freshness_sla_hours}h</span>
            )}
          </header>
          <div className="space-y-2 rounded-2xl border border-border/60 bg-muted/20 p-4 text-xs text-muted-foreground">
            {catalogEntry.default_dimensions?.length ? (
              <p>
                ????? ??????? ???????:{" "}
                <span className="font-medium text-foreground">
                  {catalogEntry.default_dimensions.join(", ")}
                </span>
              </p>
            ) : null}
            {catalogEntry.tags?.length ? (
              <p>
                ?????:{" "}
                <span className="font-medium text-foreground">{catalogEntry.tags.join(", ")}</span>
              </p>
            ) : null}
            {catalogEntry.quality_notes && <p>{catalogEntry.quality_notes}</p>}
          </div>
        </section>
      )}

    </aside>
  );
};

export default SidePanel;
