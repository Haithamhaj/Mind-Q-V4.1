"use client";

import React from "react";

import InsightCard from "./InsightCard";
import { useBiInsights } from "../data";
import type { Insight } from "../data";

type NarrativeFeedProps = {
  onOpen?: (insight: Insight) => void;
};

export const NarrativeFeed: React.FC<NarrativeFeedProps> = ({ onOpen }) => {
  const { insights, loading } = useBiInsights();

  if (loading) {
    return <div className="flex flex-col gap-3" dir="rtl">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="h-32 animate-pulse rounded-2xl bg-muted/50" />
        ))}
      </div>;
  }

  if (!insights.length) {
    return (
      <div className="rounded-2xl border border-dashed border-border/60 bg-muted/30 p-6 text-sm text-muted-foreground" dir="rtl">
        لم يتم بناء رواية تلقائية بعد. ستظهر النتائج بمجرد توفر تحليلات من المراحل 08–10.
      </div>
    );
  }

  return (
    <div className="space-y-4" dir="rtl">
      {insights.map((insight) => (
        <InsightCard
          key={insight.id}
          title={insight.title}
          summary={insight.summary ?? ""}
          severity={(insight.severity as "low" | "medium" | "high") ?? "medium"}
          drivers={insight.drivers}
          source={insight.source}
          recommendations={insight.recommendations}
          nextSteps={insight.next_steps}
          metricsContext={insight.metrics_context}
          tags={insight.tags}
          onOpen={() => onOpen?.(insight)}
        />
      ))}
    </div>
  );
};

export default NarrativeFeed;
