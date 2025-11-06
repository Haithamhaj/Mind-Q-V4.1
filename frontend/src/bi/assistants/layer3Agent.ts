"use client";

import type { Layer3Intelligence } from "../data/intelligence";

export type Layer3AgentSuggestion =
  | "network"
  | "sankey"
  | "anomalies"
  | "predictive";

export type Layer3AgentRecommendation = {
  suggestion: Layer3AgentSuggestion;
  reason: string;
  highlights: string[];
};

const KEYWORDS: Record<Layer3AgentSuggestion, string[]> = {
  network: ["network", "influence", "dependency", "relationships", "nodes"],
  sankey: ["flow", "funnel", "impact", "distribution", "sankey"],
  anomalies: ["anomaly", "spike", "outlier", "deviation", "alert", "incident"],
  predictive: ["forecast", "predict", "next", "future", "projection", "trend"],
};

export const suggestVisualization = (
  question: string,
  intelligence: Layer3Intelligence,
): Layer3AgentRecommendation => {
  const text = question.toLowerCase();
  for (const [key, vocabulary] of Object.entries(KEYWORDS) as [Layer3AgentSuggestion, string[]][]) {
    if (vocabulary.some((token) => text.includes(token))) {
      return buildRecommendation(key, intelligence);
    }
  }
  // default fallback based on data richness
  if ((intelligence.anomalies.anomalies?.length ?? 0) > 0) {
    return buildRecommendation("anomalies", intelligence);
  }
  if ((intelligence.predictive.series?.length ?? 0) > 1) {
    return buildRecommendation("predictive", intelligence);
  }
  if ((intelligence.network.nodes?.length ?? 0) > 3) {
    return buildRecommendation("network", intelligence);
  }
  return buildRecommendation("sankey", intelligence);
};

const buildRecommendation = (kind: Layer3AgentSuggestion, intelligence: Layer3Intelligence): Layer3AgentRecommendation => {
  switch (kind) {
    case "network": {
      const topNodes = intelligence.network.nodes
        .slice()
        .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        .slice(0, 3)
        .map((node) => node.label ?? node.id);
      return {
        suggestion: "network",
        reason: "العلاقات بين الـ KPIs والعوامل تظهر أعلى تركيز للإشارة.",
        highlights: topNodes,
      };
    }
    case "sankey": {
      const topFlows = intelligence.sankey.links
        .slice()
        .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
        .slice(0, 3)
        .map((link) => `${link.source} → ${link.target}`);
      return {
        suggestion: "sankey",
        reason: "تدفقات التأثير توضّح أين تتجه أعلى تغطية من التحليلات المكتشفة.",
        highlights: topFlows,
      };
    }
    case "anomalies": {
      const spikes = intelligence.anomalies.anomalies
        .map((anomaly) => `${anomaly.timestamp}: ${anomaly.label}`)
        .slice(0, 3);
      return {
        suggestion: "anomalies",
        reason: "خط الزمن يظهر الانحرافات العليا التي تتطلب متابعة تشغيلية.",
        highlights: spikes,
      };
    }
    case "predictive":
    default: {
      const forecastSeries = intelligence.predictive.series.find((serie) => serie.kind === "forecast");
      const horizon = intelligence.predictive.horizon ?? "3d";
      const points = forecastSeries?.points.slice(0, 3).map((point) => `${point.timestamp}: ${point.value}`) ?? [];
      return {
        suggestion: "predictive",
        reason: `النموذج التنبؤي جاهز لإيضاح ما سيحدث خلال ${horizon}.`,
        highlights: points,
      };
    }
  }
};

export type NaturalLanguageFilterUpdate = {
  dimension: string;
  values: string[];
};

export const interpretFilterUpdate = (question: string): NaturalLanguageFilterUpdate[] => {
  const updates: NaturalLanguageFilterUpdate[] = [];
  const normalized = question.toLowerCase();
  if (normalized.includes("vip")) {
    updates.push({ dimension: "SEGMENT", values: ["VIP"] });
  }
  if (normalized.includes("riyadh")) {
    updates.push({ dimension: "REGION", values: ["Riyadh"] });
  }
  if (normalized.includes("cod")) {
    updates.push({ dimension: "PAYMENT_METHOD", values: ["COD"] });
  }
  return updates;
};

export const planKnimeTrigger = async (
  intent: string,
): Promise<{ accepted: boolean; message: string }> => {
  if (!intent.trim()) {
    return { accepted: false, message: "لا يوجد طلب واضح لتشغيل KNIME." };
  }
  // Placeholder until backend automation endpoint is wired.
  return {
    accepted: true,
    message: "تم تسجيل الطلب. عند تفعيل واجهة تشغيل KNIME ستتم المعالجة تلقائياً.",
  };
};

export const layer3Agent = {
  suggestVisualization,
  interpretFilterUpdate,
  planKnimeTrigger,
};
