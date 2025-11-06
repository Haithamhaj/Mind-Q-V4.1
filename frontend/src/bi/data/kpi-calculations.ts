"use client";

import { useMemo } from "react";
import { BiDatasetRow } from "./types";

export interface KpiValues {
  totalOrders: number | null;
  codTotal: number | null;
  codAvg: number | null;
  codRatePct: number | null;
  slaPct: number | null;
  rtoPct: number | null;
  leadTimeP50: number | null;
  leadTimeP90: number | null;
  timezone?: string;
  currency?: string;
  lastUpdated?: string;
}

const toNumber = (value: unknown): number | null => {
  if (value === null || value === undefined) {
    return null;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const parseTimestamp = (value: unknown): number | null => {
  if (value === null || value === undefined) {
    return null;
  }
  if (value instanceof Date) {
    const time = value.getTime();
    return Number.isNaN(time) ? null : time;
  }
  if (typeof value === "number") {
    const numeric = value > 10_000_000_000 ? value : value * 1000;
    return Number.isFinite(numeric) ? numeric : null;
  }
  if (typeof value === "string") {
    if (!value.trim()) {
      return null;
    }
    const parsed = Date.parse(value);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return parseTimestamp(numeric);
    }
    return null;
  }
  return null;
};

const normaliseTimestamp = (value: unknown): string | undefined => {
  const numeric = parseTimestamp(value);
  if (numeric === null) {
    return undefined;
  }
  try {
    return new Date(numeric).toISOString();
  } catch {
    return undefined;
  }
};

export const useKpiCalculations = (dataset: BiDatasetRow[]): KpiValues =>
  useMemo(() => {
    if (!dataset || dataset.length === 0) {
      return {
        totalOrders: null,
        codTotal: null,
        codAvg: null,
        codRatePct: null,
        slaPct: null,
        rtoPct: null,
        leadTimeP50: null,
        leadTimeP90: null,
        timezone: undefined,
        currency: undefined,
        lastUpdated: undefined,
      };
    }

    let ordersSum = 0;
    let ordersFound = 0;
    let codTotalSum = 0;
    let codTotalFound = 0;
    let codAvgSum = 0;
    let codAvgCount = 0;
    let codRateSum = 0;
    let codRateCount = 0;
    let slaSum = 0;
    let slaCount = 0;
    let rtoSum = 0;
    let rtoCount = 0;
    let leadP50Sum = 0;
    let leadP50Count = 0;
    let leadP90Sum = 0;
    let leadP90Count = 0;

    let timezone: string | undefined;
    let currency: string | undefined;
    let latestTimestamp: number | null = null;

    dataset.forEach((row) => {
      const valueOf = (key: string) => (row as Record<string, unknown>)[key];

      const orders = toNumber(valueOf("kpi_orders_cnt") ?? valueOf("orders_cnt"));
      if (orders !== null) {
        ordersSum += orders;
        ordersFound += 1;
      }

      const codTotal = toNumber(valueOf("kpi_cod_total") ?? valueOf("cod_total"));
      if (codTotal !== null) {
        codTotalSum += codTotal;
        codTotalFound += 1;
      }

      const codAvg = toNumber(valueOf("kpi_cod_avg") ?? valueOf("cod_avg"));
      if (codAvg !== null) {
        codAvgSum += codAvg;
        codAvgCount += 1;
      }

      const codRate = toNumber(valueOf("kpi_cod_rate") ?? valueOf("cod_rate"));
      if (codRate !== null) {
        codRateSum += codRate;
        codRateCount += 1;
      }

      const slaPct = toNumber(valueOf("kpi_sla_pct"));
      if (slaPct !== null) {
        slaSum += slaPct;
        slaCount += 1;
      }

      const rtoPct = toNumber(valueOf("kpi_rto_pct"));
      if (rtoPct !== null) {
        rtoSum += rtoPct;
        rtoCount += 1;
      }

      const leadP50 = toNumber(valueOf("kpi_lead_time_p50"));
      if (leadP50 !== null) {
        leadP50Sum += leadP50;
        leadP50Count += 1;
      }

      const leadP90 = toNumber(valueOf("kpi_lead_time_p90"));
      if (leadP90 !== null) {
        leadP90Sum += leadP90;
        leadP90Count += 1;
      }

      if (!timezone) {
        const tzCandidate = valueOf("tz") ?? valueOf("timezone") ?? valueOf("time_zone");
        if (typeof tzCandidate === "string" && tzCandidate.trim()) {
          timezone = tzCandidate.trim();
        }
      }

      if (!currency) {
        const currencyCandidate = valueOf("currency") ?? valueOf("Currency");
        if (typeof currencyCandidate === "string" && currencyCandidate.trim()) {
          currency = currencyCandidate.trim();
        }
      }

      const timestampCandidate =
        parseTimestamp(valueOf("ts")) ??
        parseTimestamp(valueOf("timestamp")) ??
        parseTimestamp(valueOf("order_date")) ??
        parseTimestamp(valueOf("date"));

      if (timestampCandidate !== null && (latestTimestamp === null || timestampCandidate > latestTimestamp)) {
        latestTimestamp = timestampCandidate;
      }
    });

    const average = (sum: number, count: number): number | null => (count > 0 ? sum / count : null);

    return {
      totalOrders: ordersFound > 0 ? ordersSum : null,
      codTotal: codTotalFound > 0 ? codTotalSum : null,
      codAvg: average(codAvgSum, codAvgCount),
      codRatePct: (() => {
        const avgRate = average(codRateSum, codRateCount);
        return avgRate !== null ? avgRate * 100 : null;
      })(),
      slaPct: (() => {
        const avgSla = average(slaSum, slaCount);
        return avgSla !== null ? avgSla * 100 : null;
      })(),
      rtoPct: (() => {
        const avgRto = average(rtoSum, rtoCount);
        return avgRto !== null ? avgRto * 100 : null;
      })(),
      leadTimeP50: average(leadP50Sum, leadP50Count),
      leadTimeP90: average(leadP90Sum, leadP90Count),
      timezone,
      currency,
      lastUpdated: latestTimestamp !== null ? new Date(latestTimestamp).toISOString() : undefined,
    };
  }, [dataset]);

export const formatCurrency = (
  value: number | null | undefined,
  currencyLabel: string = "ر.س",
): string => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "غير متاح";
  }
  try {
    const formatted = new Intl.NumberFormat("ar-SA", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
    return `${formatted} ${currencyLabel}`;
  } catch {
    return `${value.toFixed(2)} ${currencyLabel}`;
  }
};

export const formatNumber = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "غير متاح";
  }
  try {
    return new Intl.NumberFormat("ar-SA", {
      maximumFractionDigits: 0,
    }).format(Math.round(value));
  } catch {
    return value.toFixed(0);
  }
};

export const formatPercentage = (value: number | null | undefined, digits = 1): string => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "غير متاح";
  }
  return `${value.toFixed(digits)}%`;
};
