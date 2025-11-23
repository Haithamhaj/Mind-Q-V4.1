"use client";

import React, { useMemo } from "react";
import clsx from "clsx";

import { useBiData } from "../data";

const MAX_PER_DIMENSION = 40;
const MAX_FILTERS_TO_SHOW = 12; // Maximum number of filter dimensions to display
const MIN_UNIQUE_VALUES = 2; // Minimum unique values to be useful
const MAX_UNIQUE_VALUES = 100; // Maximum unique values to avoid overwhelming UI
const MIN_COMPLETENESS = 0.1; // At least 10% of rows should have values

/**
 * Intelligently selects the most useful dimensions for filtering
 * based on data characteristics:
 * 1. Cardinality: Not too few (boring) or too many (overwhelming)
 * 2. Completeness: Has enough non-null values
 * 3. Business relevance: Prioritizes common business fields
 */
const selectFilterDimensions = (
  allDimensions: Array<{ name: string }>,
  dataset: Array<Record<string, unknown>>,
): Array<{ name: string; score: number }> => {
  if (!dataset.length) return [];

  const sampleSize = Math.min(2000, dataset.length);
  const sample = dataset.slice(0, sampleSize);

  const dimensionScores = allDimensions.map((dim) => {
    const name = dim.name;
    const values = new Set<string>();
    let nonNullCount = 0;

    sample.forEach((row) => {
      const raw = row[name];
      if (raw !== undefined && raw !== null && String(raw).trim()) {
        values.add(String(raw));
        nonNullCount++;
      }
    });

    const uniqueCount = values.size;
    const completeness = nonNullCount / sampleSize;

    // Skip if not useful
    if (uniqueCount < MIN_UNIQUE_VALUES || uniqueCount > MAX_UNIQUE_VALUES || completeness < MIN_COMPLETENESS) {
      return { name, score: 0 };
    }

    // Calculate score based on multiple factors
    let score = 0;

    // 1. Cardinality score: prefer moderate number of unique values (5-30 is ideal)
    const idealCardinality = 15;
    const cardinalityScore = 1 - Math.abs(uniqueCount - idealCardinality) / idealCardinality;
    score += Math.max(0, cardinalityScore) * 40;

    // 2. Completeness score: prefer columns with more data
    score += completeness * 30;

    // 3. Business relevance: boost common business fields
    const businessKeywords = [
      'status', 'origin', 'destination', 'type', 'mode', 'payment',
      'category', 'region', 'city', 'hub', 'carrier', 'company',
      'area', 'zone', 'system', 'channel'
    ];
    const nameLower = name.toLowerCase();
    const hasBusinessKeyword = businessKeywords.some(keyword => nameLower.includes(keyword));
    if (hasBusinessKeyword) {
      score += 30;
    }

    return { name, score };
  });

  // Sort by score and return top dimensions
  return dimensionScores
    .filter(d => d.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_FILTERS_TO_SHOW);
};

export const FilterBar: React.FC = () => {
  const { dimensions, dataset, filters, setFilter, loading } = useBiData();

  const categorical = useMemo(() => {
    const allCategorical = dimensions.categorical ?? [];
    if (!allCategorical.length || !dataset.length) {
      return [];
    }

    // Dynamically select the best dimensions for filtering
    const selectedDimensions = selectFilterDimensions(allCategorical, dataset);

    // Return dimensions in order of usefulness
    return selectedDimensions.map(sd =>
      allCategorical.find(d => d.name === sd.name)!
    ).filter(Boolean);
  }, [dimensions.categorical, dataset]);

  const options = useMemo(() => {
    const lookup: Record<string, string[]> = {};
    categorical.forEach((dimension) => {
      const name = dimension.name;
      const values = new Set<string>();
      dataset.slice(0, 2000).forEach((row) => {
        const raw = row[name];
        if (raw !== undefined && raw !== null) {
          values.add(String(raw));
        }
      });
      lookup[name] = Array.from(values).sort((a, b) => a.localeCompare(b)).slice(0, MAX_PER_DIMENSION);
    });
    return lookup;
  }, [categorical, dataset]);

  const handleToggle = (dimension: string, value: string) => {
    const current = new Set(filters[dimension] ?? []);
    if (current.has(value)) {
      current.delete(value);
    } else {
      current.add(value);
    }
    setFilter(dimension, Array.from(current));
  };

  const handleClear = (dimension: string) => {
    setFilter(dimension, []);
  };

  if (loading) {
    return <div className="h-14 w-full animate-pulse rounded-2xl bg-muted/50" aria-hidden="true" />;
  }

  if (!categorical.length) {
    return (
      <div className="rounded-2xl border border-dashed border-border/60 bg-muted/30 p-4 text-sm text-muted-foreground" dir="rtl">
        لا توجد أبعاد تصنيفية متاحة للتصفية في الوقت الحالي.
      </div>
    );
  }

  return (
    <div className="flex w-full flex-wrap items-center gap-3" dir="rtl">
      {categorical.map((dimension) => {
        const values = options[dimension.name] ?? [];
        if (!values.length) {
          return null;
        }
        const activeValues = filters[dimension.name] ?? [];
        return (
          <details
            key={dimension.name}
            className={clsx(
              "group relative min-w-[160px] flex-1 rounded-2xl border border-border/60 bg-background/70 p-3 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md",
              activeValues.length > 0 && "border-primary/60",
            )}
          >
            <summary className="cursor-pointer list-none text-sm font-medium text-foreground outline-none">
              <span className="flex items-center justify-between gap-2">
                <span className="truncate">{dimension.name}</span>
                {activeValues.length > 0 && <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">{activeValues.length}</span>}
              </span>
            </summary>
            <div className="absolute start-0 top-full z-10 mt-2 w-full min-w-[200px] rounded-2xl border border-border bg-background/95 p-3 shadow-xl backdrop-blur">
              <div className="mb-3 flex items-center justify-between gap-2">
                <span className="text-xs text-muted-foreground">اختر القيم</span>
                <button
                  type="button"
                  onClick={() => handleClear(dimension.name)}
                  className="text-xs font-medium text-primary transition hover:text-primary/70"
                >
                  مسح
                </button>
              </div>
              <div className="max-h-56 space-y-1 overflow-y-auto pr-1 text-sm">
                {values.map((value) => {
                  const checked = activeValues.includes(value);
                  return (
                    <label
                      key={`${dimension.name}-${value}`}
                      className={clsx(
                        "flex cursor-pointer items-center justify-between gap-3 rounded-xl px-2 py-2 transition",
                        checked ? "bg-primary/10 text-primary" : "hover:bg-muted/60",
                      )}
                    >
                      <input
                        type="checkbox"
                        className="h-3.5 w-3.5 accent-primary"
                        checked={checked}
                        onChange={() => handleToggle(dimension.name, value)}
                      />
                      <span className="flex-1 truncate text-end">{value}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          </details>
        );
      })}
    </div>
  );
};

export default FilterBar;
