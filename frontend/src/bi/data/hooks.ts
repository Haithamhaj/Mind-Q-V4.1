"use client";

import { useMemo } from "react";

import { useBiDataContext } from "./provider";
import { BiDatasetRow } from "./types";

const MAX_VALUES = 50;

export const useBiData = () => {
  return useBiDataContext();
};

export const useBiDimensions = () => {
  const { dimensions } = useBiDataContext();
  return dimensions;
};

export const useBiMetrics = () => {
  const { metrics } = useBiDataContext();
  return metrics;
};

export const useBiInsights = () => {
  const { insights, loading, insightStats } = useBiDataContext();
  return { insights, loading, insightStats };
};

export const useBiCorrelations = () => {
  const { correlations } = useBiDataContext();
  return correlations;
};

export const useDimensionValues = (dimension: string) => {
  const { dataset } = useBiDataContext();

  return useMemo(() => {
    const values = new Set<string>();
    dataset.slice(0, 1000).forEach((row: BiDatasetRow) => {
      const raw = row[dimension];
      if (raw !== undefined && raw !== null) {
        values.add(String(raw));
      }
    });
    return Array.from(values).slice(0, MAX_VALUES).sort((a, b) => a.localeCompare(b));
  }, [dataset, dimension]);
};

export const useFilteredDataset = () => {
  const { dataset, filters } = useBiDataContext();
  return useMemo(() => {
    const entries = Object.entries(filters).filter(([, values]) => values.length > 0);
    if (!entries.length) {
      return dataset;
    }
    return dataset.filter((row) =>
      entries.every(([dimension, values]) => {
        const raw = row[dimension];
        if (raw === undefined || raw === null) {
          return false;
        }
        return values.includes(String(raw));
      }),
    );
  }, [dataset, filters]);
};

export const useBiSchemaGlossary = () => {
  const { schemaGlossary, refreshSchemaGlossary } = useBiDataContext();
  return {
    ...schemaGlossary,
    refresh: refreshSchemaGlossary,
  };
};

