import { z } from "zod";

const metricsSummarySchema = z.object({
  focus: z.string(),
  current: z.number(),
  baseline: z.number().optional(),
  delta: z.number().optional(),
  deltaPct: z.number().optional(),
  unit: z.string().optional(),
  target: z.number().optional(),
});

const baseInsightSchema = z.object({
  id: z.string(),
  title: z.string(),
  summary: z.string(),
  narrative: z.string().optional(),
  focusMetric: z.string().optional(),
  confidence: z.enum(["low", "medium", "high"]).optional(),
  filters: z.record(z.string(), z.array(z.string())).optional(),
  tags: z.array(z.string()).optional(),
  metrics: metricsSummarySchema.optional(),
});

export const heatmapInsightSchema = baseInsightSchema.extend({
  chartType: z.literal("heatmap"),
  dataset: z.object({
    xAxis: z.array(z.string()),
    yAxis: z.array(z.string()),
    cells: z
      .array(
        z.object({
          x: z.string(),
          y: z.string(),
          value: z.number(),
        }),
      )
      .min(1),
    xLabel: z.string().optional(),
    yLabel: z.string().optional(),
    colorLabel: z.string().optional(),
  }),
});

export const boxPlotInsightSchema = baseInsightSchema.extend({
  chartType: z.literal("boxplot"),
  dataset: z.object({
    categories: z.array(z.string()).min(1),
    samples: z
      .array(
        z.object({
          category: z.string(),
          values: z.array(z.number()).min(4),
        }),
      )
      .min(1),
    unit: z.string().optional(),
    label: z.string().optional(),
  }),
});

export const waterfallInsightSchema = baseInsightSchema.extend({
  chartType: z.literal("waterfall"),
  dataset: z.object({
    unit: z.string().optional(),
    steps: z
      .array(
        z.object({
          label: z.string(),
          value: z.number().optional(),
          type: z.enum(["baseline", "increase", "decrease", "total"]),
          annotation: z.string().optional(),
        }),
      )
      .min(2),
  }),
});

export const scatterInsightSchema = baseInsightSchema.extend({
  chartType: z.literal("scatter"),
  dataset: z.object({
    xKey: z.string(),
    yKey: z.string(),
    sizeKey: z.string().optional(),
    categoryKey: z.string().optional(),
    axisLabels: z
      .object({
        x: z.string(),
        y: z.string(),
        size: z.string().optional(),
      })
      .optional(),
    points: z
      .array(
        z.object({
          id: z.string(),
          x: z.number(),
          y: z.number(),
          size: z.number().optional(),
          category: z.string().optional(),
          label: z.string().optional(),
        }),
      )
      .min(1),
  }),
});

export const multiAxisLineInsightSchema = baseInsightSchema.extend({
  chartType: z.literal("multiAxisLine"),
  dataset: z.object({
    xAxis: z.array(z.string()).min(2),
    leftYAxis: z.object({
      label: z.string().optional(),
      unit: z.string().optional(),
      series: z
        .array(
          z.object({
            name: z.string(),
            data: z.array(z.number()),
          }),
        )
        .min(1),
    }),
    rightYAxis: z
      .object({
        label: z.string().optional(),
        unit: z.string().optional(),
        series: z
          .array(
            z.object({
              name: z.string(),
              data: z.array(z.number()),
            }),
          )
          .min(1),
      })
      .optional(),
  }),
});

export const layer2InsightSchema = z.discriminatedUnion("chartType", [
  heatmapInsightSchema,
  boxPlotInsightSchema,
  waterfallInsightSchema,
  scatterInsightSchema,
  multiAxisLineInsightSchema,
]);

export type Layer2Insight = z.infer<typeof layer2InsightSchema>;
export type Layer2HeatmapInsight = z.infer<typeof heatmapInsightSchema>;
export type Layer2BoxPlotInsight = z.infer<typeof boxPlotInsightSchema>;
export type Layer2WaterfallInsight = z.infer<typeof waterfallInsightSchema>;
export type Layer2ScatterInsight = z.infer<typeof scatterInsightSchema>;
export type Layer2MultiAxisLineInsight = z.infer<typeof multiAxisLineInsightSchema>;

const rawLayer2Insights: Layer2Insight[] = [
  {
    id: "layer2-heatmap-cod-variance",
    chartType: "heatmap",
    title: "COD Variance by Region & Segment",
    summary: "Segment-level variance shows Riyadh VIP and Jeddah Marketplace driving the volatility spike versus Q3 baseline.",
    narrative:
      "Variance is clustering around high-value COD in Riyadh and Jeddah. Marketplace sellers in Jeddah show 14% deviation, suggesting price sensitivity or ungoverned COD promotions.",
    metrics: {
      focus: "cod_variance_pct",
      current: 7.8,
      baseline: 4.3,
      delta: 3.5,
      deltaPct: 0.81,
      unit: "%",
    },
    confidence: "high",
    filters: {
      Segment: ["VIP", "Prime", "Marketplace", "Standard"],
      "Payment Method": ["COD", "Prepaid"],
      "Time Range": ["2025-Q1"],
    },
    dataset: {
      xAxis: ["Riyadh", "Jeddah", "Dammam", "Mecca", "Medina"],
      yAxis: ["VIP", "Prime", "Marketplace", "Standard"],
      xLabel: "Region",
      yLabel: "Customer Segment",
      colorLabel: "Variance (%)",
      cells: [
        { x: "Riyadh", y: "VIP", value: 12.5 },
        { x: "Riyadh", y: "Prime", value: 8.9 },
        { x: "Riyadh", y: "Marketplace", value: 10.6 },
        { x: "Riyadh", y: "Standard", value: 6.8 },
        { x: "Jeddah", y: "VIP", value: 10.1 },
        { x: "Jeddah", y: "Prime", value: 11.3 },
        { x: "Jeddah", y: "Marketplace", value: 14.2 },
        { x: "Jeddah", y: "Standard", value: 9.4 },
        { x: "Dammam", y: "VIP", value: 6.1 },
        { x: "Dammam", y: "Prime", value: 5.4 },
        { x: "Dammam", y: "Marketplace", value: 7.2 },
        { x: "Dammam", y: "Standard", value: 4.9 },
        { x: "Mecca", y: "VIP", value: 8.7 },
        { x: "Mecca", y: "Prime", value: 7.9 },
        { x: "Mecca", y: "Marketplace", value: 9.6 },
        { x: "Mecca", y: "Standard", value: 6.2 },
        { x: "Medina", y: "VIP", value: 5.5 },
        { x: "Medina", y: "Prime", value: 4.8 },
        { x: "Medina", y: "Marketplace", value: 6.7 },
        { x: "Medina", y: "Standard", value: 4.2 },
      ],
    },
  },
  {
    id: "layer2-boxplot-delivery-latency",
    chartType: "boxplot",
    title: "Delivery Latency Distribution",
    summary: "Northern corridor still exhibits wider delivery spread and heavier tails, indicating capacity constraints compared to other hubs.",
    metrics: {
      focus: "delivery_days",
      current: 2.8,
      baseline: 3.1,
      delta: -0.3,
      deltaPct: -0.097,
      unit: "days",
    },
    confidence: "medium",
    filters: {
      Segment: ["VIP", "Prime", "Standard"],
      "Payment Method": ["COD"],
      "Time Range": ["2025-03"],
    },
    dataset: {
      label: "Last-mile delivery lead time",
      unit: "days",
      categories: ["Central Hub", "Western Hub", "Southern Hub", "Northern Corridor"],
      samples: [
        {
          category: "Central Hub",
          values: [1.6, 1.8, 1.9, 2.1, 2.0, 2.2, 2.3, 1.7, 1.9, 2.0, 2.1],
        },
        {
          category: "Western Hub",
          values: [2.3, 2.1, 2.4, 2.6, 2.2, 2.1, 2.4, 2.7, 2.5, 2.6, 2.3],
        },
        {
          category: "Southern Hub",
          values: [2.2, 2.4, 2.1, 2.5, 2.3, 2.6, 2.5, 2.7, 2.8, 2.3, 2.2],
        },
        {
          category: "Northern Corridor",
          values: [2.9, 3.1, 3.4, 3.6, 3.8, 3.3, 3.5, 3.9, 3.7, 3.2, 3.6],
        },
      ],
    },
  },
  {
    id: "layer2-waterfall-cod-revenue",
    chartType: "waterfall",
    title: "COD Revenue Bridge (Q3 → Q4 Projection)",
    summary:
      "Premium segment uplift offsets incentives drag, but returns are still eroding 13% of projected COD revenue.",
    metrics: {
      focus: "cod_revenue_million_sar",
      current: 20.3,
      baseline: 16.2,
      delta: 4.1,
      deltaPct: 0.253,
      unit: "million SAR",
    },
    confidence: "medium",
    filters: {
      Segment: ["Premium", "Standard"],
      "Payment Method": ["COD"],
      "Time Range": ["2024-Q4 Projection"],
    },
    dataset: {
      unit: "million SAR",
      steps: [
        { label: "Baseline Q3 COD", value: 16.2, type: "baseline", annotation: "Ending COD revenue in Q3" },
        { label: "Premium Segment Uplift", value: 2.4, type: "increase", annotation: "Targeted offers & bundles" },
        { label: "New City Launches", value: 1.8, type: "increase", annotation: "Taif + Yanbu expansion" },
        { label: "Returns & Cancellations", value: -2.1, type: "decrease", annotation: "Reverse logistics exposure" },
        { label: "Delivery Incentives", value: -0.7, type: "decrease", annotation: "Cash-back to COD couriers" },
        { label: "Projected Q4 COD", type: "total", annotation: "Scenario projection after interventions" },
      ],
    },
  },
  {
    id: "layer2-scatter-returns",
    chartType: "scatter",
    title: "Return Rate vs COD Volume",
    summary:
      "COD-heavy regions with >15K weekly orders sit above 8% return rate, spotlighting Jeddah VIP as the priority for workflow fixes.",
    metrics: {
      focus: "return_rate_pct",
      current: 7.4,
      baseline: 6.1,
      delta: 1.3,
      deltaPct: 0.213,
      unit: "%",
    },
    confidence: "high",
    filters: {
      Segment: ["VIP", "Marketplace", "Standard"],
      "Payment Method": ["COD"],
      "Time Range": ["Rolling 6 weeks"],
    },
    dataset: {
      xKey: "weeklyOrdersK",
      yKey: "returnRatePct",
      sizeKey: "avgCodTicket",
      categoryKey: "region",
      axisLabels: {
        x: "Weekly Orders (thousands)",
        y: "Return Rate (%)",
        size: "Avg COD Ticket (SAR)",
      },
      points: [
        { id: "riyadh-vip", label: "Riyadh VIP", x: 18.6, y: 7.1, size: 462, category: "Riyadh" },
        { id: "riyadh-marketplace", label: "Riyadh Marketplace", x: 16.2, y: 6.4, size: 318, category: "Riyadh" },
        { id: "jeddah-vip", label: "Jeddah VIP", x: 15.4, y: 8.6, size: 441, category: "Jeddah" },
        { id: "jeddah-marketplace", label: "Jeddah Marketplace", x: 14.1, y: 8.9, size: 305, category: "Jeddah" },
        { id: "dammam-standard", label: "Dammam Standard", x: 9.8, y: 6.1, size: 214, category: "Dammam" },
        { id: "mecca-standard", label: "Mecca Standard", x: 11.3, y: 5.8, size: 236, category: "Mecca" },
        { id: "medina-standard", label: "Medina Standard", x: 7.2, y: 4.9, size: 198, category: "Medina" },
      ],
    },
  },
  {
    id: "layer2-multi-axis-line-cod-trends",
    chartType: "multiAxisLine",
    title: "COD Orders vs Return Rate (8-week trend)",
    summary:
      "COD orders are tracking +9% since January, while return rate plateaued at ~7.5%, signalling diminishing returns from incentive spend.",
    metrics: {
      focus: "cod_orders_trend",
      current: 18.4,
      baseline: 16.8,
      delta: 1.6,
      deltaPct: 0.095,
      unit: "thousand orders",
    },
    filters: {
      Segment: ["All"],
      "Payment Method": ["COD", "Prepaid"],
      "Time Range": ["Last 8 weeks"],
    },
    dataset: {
      xAxis: ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"],
      leftYAxis: {
        label: "Orders (thousand)",
        unit: "k",
        series: [
          { name: "COD Orders", data: [16.8, 17.2, 17.9, 18.5, 19.1, 18.7, 18.3, 18.4] },
          { name: "Prepaid Orders", data: [12.1, 12.4, 12.7, 12.9, 13.1, 13.4, 13.2, 13.5] },
        ],
      },
      rightYAxis: {
        label: "Return Rate (%)",
        unit: "%",
        series: [
          { name: "COD Return Rate", data: [7.8, 7.5, 7.4, 7.2, 7.5, 7.6, 7.4, 7.3] },
          { name: "Prepaid Return Rate", data: [4.9, 4.7, 4.6, 4.5, 4.6, 4.4, 4.5, 4.4] },
        ],
      },
    },
  },
];

export const layer2Insights = layer2InsightSchema.array().parse(rawLayer2Insights);

export type Layer2InsightCollection = typeof layer2Insights;
