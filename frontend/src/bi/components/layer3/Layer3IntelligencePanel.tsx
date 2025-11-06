"use client";

import React from "react";
import clsx from "clsx";
import type { Layer3Intelligence } from "../../data/intelligence";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import NetworkGraph from "./NetworkGraph";
import SankeyChart from "./SankeyChart";
import AnomalyTimelineChart from "./AnomalyTimelineChart";
import PredictiveTrendsChart from "./PredictiveTrendsChart";

type Layer3IntelligencePanelProps = {
  intelligence: Layer3Intelligence;
  className?: string;
};

export const Layer3IntelligencePanel: React.FC<Layer3IntelligencePanelProps> = ({ intelligence, className }) => {
  const anomalyCount = intelligence.anomalies.anomalies.length;
  return (
    <section
      className={clsx(
        "flex flex-col gap-6 rounded-2xl border border-border/60 bg-background/70 p-4 shadow-sm",
        className,
      )}
      dir="rtl"
    >
      <header className="flex flex-col gap-2 text-start">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-foreground">تحليلات الطبقة الثالثة</h2>
            <p className="text-sm text-muted-foreground">
              تمثيل الشبكات، تدفقات التأثير، خط زمني للانحرافات، وتوقعات الأداء المبنية على نتائج Stage 08 وKNIME.
            </p>
          </div>
          <Badge variant="secondary" className="text-xs font-medium">
            Run: {intelligence.run}
          </Badge>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="border-border/40 bg-background/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-start">شبكة التأثير</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              KPIs والعوامل الأعلى تأثيراً مع قوة الإشارة المكتشفة.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <NetworkGraph data={intelligence.network} />
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-background/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-start">تدفقات التأثير</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              انتقال الإشارات من KPIs إلى شرائح التشغيل وفق تغطية Stage 08.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SankeyChart data={intelligence.sankey} />
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-background/80 shadow-sm">
          <CardHeader className="flex items-start justify-between pb-3">
            <div>
              <CardTitle className="text-base font-semibold text-start">خط زمني للانحرافات</CardTitle>
              <CardDescription className="text-sm text-muted-foreground">
                رصد اللحظات الحرجة ومؤشرات الخطر بناءً على z-score والاتجاهات اليومية.
              </CardDescription>
            </div>
            <Badge variant={anomalyCount > 2 ? "destructive" : "secondary"}>{anomalyCount} إشارات</Badge>
          </CardHeader>
          <CardContent>
            <AnomalyTimelineChart data={intelligence.anomalies} />
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-background/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-start">توقعات الأداء</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">
              مقارنة الأداء الفعلي مقابل التوقعات لثلاثة أيام قادمة.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PredictiveTrendsChart data={intelligence.predictive} />
          </CardContent>
        </Card>
      </div>
    </section>
  );
};

export default Layer3IntelligencePanel;
