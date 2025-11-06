"use client";

import { buildBilingualLabel, resolveFieldLabel } from "../charts/shared/labels";
import type { Layer1ChartType } from "../charts/layer1";
import type { DimensionsCatalog, MetricSpec } from "../data";

export type Layer1ColumnDescriptor = {
  key: string;
  labelEn: string;
  labelAr: string;
  dtype: "number" | "string" | "boolean" | "datetime";
  sampleValues: string[];
  uniqueCount: number;
  numericSummary?: { min: number; max: number; avg: number };
  aliases: string[];
};

export type Layer1AgentRequest = {
  question: string;
  dataset: Record<string, unknown>[];
  filters: Record<string, string[]>;
  metrics: MetricSpec[];
  dimensions: DimensionsCatalog;
};

export type Layer1AgentResponse = {
  reply: string;
  filtersToSet?: Record<string, string[]>;
  filtersToClear?: string[];
  chartRecommendation?: {
    type: Layer1ChartType;
    metricKey?: string;
    dimensionKey?: string;
    x: string;
    y: string[];
    secondaryY?: string[];
    reason: string;
  };
  columnExplanation?: {
    key: string;
    label: string;
    lines: string[];
  };
};

const MAX_SAMPLE_ROWS = 400;
const MAX_SAMPLE_VALUES = 12;
const NUMBER_REGEX = /-?\d+(?:[.,]\d+)?/g;

const normalize = (value: string): string =>
  value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u064B-\u0652]/g, "")
    .trim();

const analyseDataset = (dataset: Record<string, unknown>[]): Layer1ColumnDescriptor[] => {
  const entries = dataset.slice(0, MAX_SAMPLE_ROWS);
  const stats = new Map<
    string,
    {
      total: number;
      numericCount: number;
      booleanCount: number;
      dateCount: number;
      numericValues: number[];
      uniqueValues: Set<string>;
      samples: Set<string>;
    }
  >();

  entries.forEach((row) => {
    Object.entries(row).forEach(([key, raw]) => {
      if (raw === null || raw === undefined) {
        return;
      }
      const bucket =
        stats.get(key) ??
        {
          total: 0,
          numericCount: 0,
          booleanCount: 0,
          dateCount: 0,
          numericValues: [],
          uniqueValues: new Set<string>(),
          samples: new Set<string>(),
        };
      bucket.total += 1;

      const valueString = String(raw).trim();
      bucket.uniqueValues.add(valueString);
      if (bucket.samples.size < MAX_SAMPLE_VALUES) {
        bucket.samples.add(valueString);
      }

      if (typeof raw === "number" && Number.isFinite(raw)) {
        bucket.numericCount += 1;
        bucket.numericValues.push(raw);
      } else if (typeof raw === "boolean") {
        bucket.booleanCount += 1;
      } else if (raw instanceof Date && !Number.isNaN(raw.getTime())) {
        bucket.dateCount += 1;
      } else if (typeof raw === "string") {
        const trimmed = raw.trim();
        const numericCandidate = Number(trimmed.replace(/[%\s,]+/g, ""));
        if (!Number.isNaN(numericCandidate) && trimmed.length <= 15) {
          bucket.numericCount += 1;
          bucket.numericValues.push(numericCandidate);
        } else {
          const parsed = Date.parse(trimmed);
          if (!Number.isNaN(parsed)) {
            bucket.dateCount += 1;
          } else {
            const lc = trimmed.toLowerCase();
            if (["true", "false", "yes", "no", "1", "0"].includes(lc)) {
              bucket.booleanCount += 1;
            }
          }
        }
      }

      stats.set(key, bucket);
    });
  });

  const descriptors: Layer1ColumnDescriptor[] = [];

  for (const [key, summary] of stats.entries()) {
    const total = summary.total || 1;
    let dtype: Layer1ColumnDescriptor["dtype"] = "string";
    if (summary.numericCount / total >= 0.6) {
      dtype = "number";
    } else if (summary.dateCount / total >= 0.4) {
      dtype = "datetime";
    } else if (summary.booleanCount / total >= 0.6) {
      dtype = "boolean";
    }

    const { en, ar } = resolveFieldLabel(key);
    const sampleValues = Array.from(summary.samples.values());

    const descriptor: Layer1ColumnDescriptor = {
      key,
      labelEn: en,
      labelAr: ar,
      dtype,
      sampleValues,
      uniqueCount: summary.uniqueValues.size,
      aliases: [
        normalize(key),
        normalize(en),
        normalize(ar),
        normalize(en.replace(/\s+/g, "")),
        normalize(ar.replace(/\s+/g, "")),
      ].filter(Boolean),
    };

    if (dtype === "number" && summary.numericValues.length) {
      const min = Math.min(...summary.numericValues);
      const max = Math.max(...summary.numericValues);
      const avg = summary.numericValues.reduce((acc, value) => acc + value, 0) / summary.numericValues.length;
      descriptor.numericSummary = { min, max, avg };
    }

    descriptors.push(descriptor);
  }

  return descriptors.sort((a, b) => a.key.localeCompare(b.key));
};

const findColumn = (text: string, columns: Layer1ColumnDescriptor[]): Layer1ColumnDescriptor | undefined => {
  let best: Layer1ColumnDescriptor | undefined;
  let score = 0;
  columns.forEach((column) => {
    const matches = column.aliases.some((alias) => alias && text.includes(alias));
    if (matches && column.labelEn.length > score) {
      best = column;
      score = column.labelEn.length;
    }
  });
  return best;
};

const pickMetric = (question: string, metrics: MetricSpec[], numericColumns: Layer1ColumnDescriptor[]) => {
  const lc = question.toLowerCase();
  const DEFAULT_METRIC_PRIORITY = ["amount", "cod", "orders", "value"];

  const findByKeyword = (keywords: string[]) =>
    metrics.find((metric) => {
      const haystack = `${metric.id} ${metric.title ?? ""}`.toLowerCase();
      return keywords.some((keyword) => haystack.includes(keyword));
    });

  const codMetric = findByKeyword(["cod"]);
  if (codMetric && lc.includes("cod")) {
    return codMetric.id;
  }

  for (const keyword of DEFAULT_METRIC_PRIORITY) {
    const metric = findByKeyword([keyword]);
    if (metric) {
      if (lc.includes(keyword)) {
        return metric.id;
      }
    }
  }

  const numericColumnMatch = numericColumns.find((column) => lc.includes(normalize(column.key)));
  if (numericColumnMatch) {
    const metric = metrics.find((item) => item.id === numericColumnMatch.key || item.title?.includes(numericColumnMatch.labelEn));
    if (metric) {
      return metric.id;
    }
  }

  return metrics[0]?.id ?? null;
};

const determineChartType = (column: Layer1ColumnDescriptor | undefined, question: string): Layer1ChartType => {
  const lc = question.toLowerCase();
  if (lc.includes("pie") || lc.includes("donut") || lc.includes("حصة") || lc.includes("نسبة")) {
    return "pie";
  }
  if (lc.includes("funnel") || lc.includes("مسار")) {
    return "funnel";
  }
  if (column?.dtype === "datetime" || lc.includes("trend") || lc.includes("زمن") || lc.includes("يوم")) {
    return "line";
  }
  if (lc.includes("treemap") || lc.includes("مساحة") || lc.includes("هرمي")) {
    return "treemap";
  }
  if (lc.includes("combo") || lc.includes("خط وعمود")) {
    return "combo";
  }
  if (lc.includes("area") || lc.includes("مساحة")) {
    return "area";
  }
  return "bar";
};

const buildColumnExplanation = (column: Layer1ColumnDescriptor): Layer1AgentResponse["columnExplanation"] => {
  const lines: string[] = [];
  lines.push(`• النوع: ${column.dtype === "number" ? "رقمي" : column.dtype === "datetime" ? "زمني" : column.dtype === "boolean" ? "قيمي (نعم/لا)" : "نصي"}.`);
  if (column.numericSummary) {
    const formatter = new Intl.NumberFormat("ar-SA", { maximumFractionDigits: 2 });
    lines.push(
      `• نطاق القيم: ${formatter.format(column.numericSummary.min)} → ${formatter.format(column.numericSummary.max)}`,
    );
    lines.push(`• المتوسط التقريبي: ${formatter.format(column.numericSummary.avg)}.`);
  }
  if (column.sampleValues.length) {
    lines.push(`• أمثلة: ${column.sampleValues.slice(0, 3).map((value) => `"${value}"`).join("، ")}.`);
  }
  lines.push(`• عدد القيم المميزة (تقريبي): ${column.uniqueCount}.`);

  return {
    key: column.key,
    label: buildBilingualLabel(column.key),
    lines,
  };
};

const selectFilterValues = (
  question: string,
  column: Layer1ColumnDescriptor,
): string[] => {
  const lc = question.toLowerCase();
  const matches: string[] = [];

  column.sampleValues.forEach((sample) => {
    const normalizedSample = normalize(sample);
    if (normalizedSample && lc.includes(normalizedSample)) {
      matches.push(sample);
    }
  });

  if (!matches.length && column.dtype === "number") {
    const numbers = question.match(NUMBER_REGEX);
    if (numbers) {
      matches.push(...numbers.map((value) => value.replace(",", ".")));
    }
  }

  return Array.from(new Set(matches));
};

const COLUMN_LIST_KEYWORDS = ["الأعمدة", "الاعمدة", "fields", "columns", "available"];
const EXPLAIN_KEYWORDS = ["شرح", "اشرح", "ما هو", "what is", "explain"];
const FILTER_KEYWORDS = ["فلتر", "تصفية", "حصر", "filter", "عرض فقط", "إظهار فقط", "فقط"];
const CLEAR_FILTER_KEYWORDS = ["الغاء الفلاتر", "مسح الفلاتر", "بدون فلتر", "clear filter", "reset filter", "إزالة الفلاتر", "إلغاء الفلتر"];
const CHART_KEYWORDS = ["رسم", "رسمه", "chart", "عرض", "visual", "trend", "مخطط", "بيان", "تحليل"];
const RESET_ALL_KEYWORDS = ["الكل", "الجميع", "all"];

export const runLayer1Agent = (request: Layer1AgentRequest): Layer1AgentResponse => {
  const { question, dataset, filters, metrics } = request;
  const trimmedQuestion = question.trim();
  if (!trimmedQuestion) {
    return {
      reply: "لم أستلم سؤالك. جرّب مثلاً: \"فلتر الوجهة على جدة\" أو \"اشرح حقل COD_AMOUNT\".",
    };
  }

  const lowercase = normalize(trimmedQuestion);
  const columns = analyseDataset(dataset);
  const numericColumns = columns.filter((column) => column.dtype === "number");

  const matchedColumn = findColumn(lowercase, columns);
  const response: Layer1AgentResponse = {
    reply: "",
  };

  if (COLUMN_LIST_KEYWORDS.some((keyword) => lowercase.includes(normalize(keyword)))) {
    const topColumns = columns.slice(0, 8);
    const entries = topColumns
      .map((column) => `• ${buildBilingualLabel(column.key)} (${column.dtype})`)
      .join("\n");
    response.reply = `هذه أبرز الحقول المتاحة:\n${entries}\nيمكنك مثلاً أن تقول: "فلتر ${topColumns[0]?.labelAr ?? ""} على قيمة محددة" أو "اشرح ${topColumns[1]?.labelAr ?? ""}".`;
    return response;
  }

  const wantsExplanation = EXPLAIN_KEYWORDS.some((keyword) => lowercase.includes(normalize(keyword)));
  if (wantsExplanation && matchedColumn) {
    const explanation = buildColumnExplanation(matchedColumn);
    response.columnExplanation = explanation;
    response.reply = `الحقل ${explanation.label}:\n${explanation.lines.join("\n")}\nيمكنك طلب رسم بياني أو فلترة لهذا الحقل أيضاً.`;
    return response;
  }

const wantsClear = CLEAR_FILTER_KEYWORDS.some((keyword) => lowercase.includes(normalize(keyword)));
  if (wantsClear) {
    if (!Object.keys(filters).length) {
      response.reply = "لا توجد فلاتر فعالة حالياً. يمكنك ضبط فلتر بقول: \"فلتر الوجهة على جدة\".";
      return response;
    }
    if (matchedColumn) {
      response.filtersToClear = [matchedColumn.key];
      response.reply = `تمت إزالة الفلاتر عن الحقل ${buildBilingualLabel(matchedColumn.key)}.`;
    } else {
      const clearAll = RESET_ALL_KEYWORDS.some((keyword) => lowercase.includes(normalize(keyword)));
      response.filtersToClear = clearAll ? Object.keys(filters) : Object.keys(filters);
      response.reply = clearAll ? "تمت إزالة جميع الفلاتر الحالية." : "تمت إزالة الفلاتر المحددة.";
    }
    return response;
  }

  const wantsFilter = FILTER_KEYWORDS.some((keyword) => lowercase.includes(normalize(keyword)));
  if (wantsFilter) {
    if (!matchedColumn) {
      response.reply =
        "لم أتمكن من التعرف على الحقل المطلوب للفلترة. اذكر اسم الحقل بشكل أوضح، مثلاً: \"فلتر الوجهة على جدة\".";
      return response;
    }
    const selectedValues = selectFilterValues(lowercase, matchedColumn);
    if (!selectedValues.length) {
      response.reply = `لم أجد قيمة مناسبة من أمثلة ${buildBilingualLabel(matchedColumn.key)} داخل السؤال. جرّب ذكر قيمة موجودة مثل: ${matchedColumn.sampleValues.slice(0, 3).join("، ")}.`;
      return response;
    }
    response.filtersToSet = { [matchedColumn.key]: selectedValues };
    response.reply = `تم ضبط فلتر الحقل ${buildBilingualLabel(matchedColumn.key)} على القيم: ${selectedValues.join(", ")}.`;
    return response;
  }

  const wantsChart = CHART_KEYWORDS.some((keyword) => lowercase.includes(normalize(keyword)));
  if (wantsChart || matchedColumn) {
    const columnForChart = matchedColumn ?? columns.find((column) => column.dtype !== "number");
    const chartType = determineChartType(columnForChart, lowercase);
    const metricKey = pickMetric(lowercase, metrics, numericColumns);

    const dimensionKey =
      columnForChart && columnForChart.dtype !== "number" ? columnForChart.key : request.dimensions.categorical[0]?.name ?? columnForChart?.key ?? "destination";

    const xAxisKey =
      chartType === "line" && request.dimensions.date[0]?.name
        ? request.dimensions.date[0].name
        : dimensionKey;

    response.chartRecommendation = {
      type: chartType,
      metricKey: metricKey ?? undefined,
      dimensionKey,
      x: xAxisKey,
      y: ["value"],
      secondaryY: chartType === "combo" ? ["share"] : undefined,
      reason: columnForChart
        ? `اعتمدت على الحقل ${buildBilingualLabel(columnForChart.key)} لأنه الأكثر ارتباطاً بالسؤال.`
        : `استخدمت أول حقل متاح ${buildBilingualLabel(dimensionKey)} مع المقياس ${metricKey ? buildBilingualLabel(metricKey) : "قيمة"} .`,
    };

    response.reply = `جاهز لعرض مخطط ${chartType === "bar" ? "أعمدة" : chartType === "line" ? "خطوط" : chartType} باستخدام ${metricKey ? buildBilingualLabel(metricKey) : "قيمة"} مقابل ${buildBilingualLabel(xAxisKey)}.${columnForChart ? ` (الحقل المستهدف: ${buildBilingualLabel(columnForChart.key)})` : ""}`;
    return response;
  }

  response.reply =
    "لم أتعرف على الطلب، لكن يمكنني مساعدتك عبر:\n• قول \"شرح <اسم الحقل>\" للحصول على وصف.\n• أو \"فلتر <الحقل> على <القيمة>\" لضبط الفلاتر.\n• أو \"رسم <الحقل>\" للحصول على توصية بمخطط.";
  return response;
};
