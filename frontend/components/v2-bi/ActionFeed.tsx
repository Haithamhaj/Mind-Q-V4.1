'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useLanguage } from '@/context/language-context';

type InsightItem = {
  id: string;
  title: string;
  insight_text: string;
  severity: 'critical' | 'warning' | 'info';
  deep_dive_filters: Record<string, string | number | null | undefined>;
};

const severityIntent: Record<InsightItem['severity'], { label: string; variant: 'destructive' | 'secondary' | 'default' }> =
  {
    critical: { label: 'Critical', variant: 'destructive' },
    warning: { label: 'Warning', variant: 'secondary' },
    info: { label: 'Info', variant: 'default' },
  };

export function ActionFeed({ runId }: { runId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { translate } = useLanguage();
  const [insights, setInsights] = useState<InsightItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setInsights([]);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    fetch(`/api/v2/ml/insights/feed?run_id=${encodeURIComponent(runId)}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(translate('Failed to load insights: {error}', { error: response.status.toString() }));
        }
        return response.json();
      })
      .then((payload: InsightItem[]) => {
        if (active) {
          setInsights(payload);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err.message);
          setInsights([]);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [runId]);

  const noData = !loading && !error && insights.length === 0;

  const currentParams = useMemo(() => new URLSearchParams(searchParams.toString()), [searchParams]);

  const handleDeepDive = (filters: Record<string, string | number | null | undefined>) => {
    const next = new URLSearchParams(currentParams);
    next.set('run_id', runId);
    Object.entries(filters || {}).forEach(([key, value]) => {
      if (value === null || value === undefined || value === '') {
        return;
      }
      next.set(key, String(value));
    });
    router.push(`/data-lab?${next.toString()}`);
  };

  if (!runId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{translate('Action Feed')}</CardTitle>
          <CardDescription>{translate('Enter a run_id to load insights.')}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{translate('Action Feed')}</CardTitle>
        <CardDescription>{translate('AI-curated insights from Stage 08.')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && <p className="text-base text-muted-foreground">{translate('Loading...')}</p>}
        {error && <p className="text-base text-destructive">{error}</p>}
        {noData && <p className="text-base text-muted-foreground">{translate('No actionable items found for this run.')}</p>}
        {insights.map((insight) => {
          const severity = severityIntent[insight.severity] ?? severityIntent.info;
          return (
            <div key={insight.id} className="rounded-lg border p-4 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-lg font-semibold leading-relaxed">{insight.title}</p>
                  <p className="text-base text-muted-foreground leading-relaxed">{insight.insight_text}</p>
                  {insight.demotion_note && (
                    <p className="text-xs text-muted-foreground mt-1">{insight.demotion_note}</p>
                  )}
                </div>
                <Badge variant={severity.variant}>{severity.label}</Badge>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                {Object.entries(insight.deep_dive_filters || {}).map(([key, value]) => {
                  if (!value) {
                    return null;
                  }
                  return (
                    <Badge key={key} variant="outline">
                      {key}: {value}
                    </Badge>
                  );
                })}
              </div>
              <div className="mt-4 flex justify-end">
                <Button variant="secondary" onClick={() => handleDeepDive(insight.deep_dive_filters || {})}>
                  {translate('Deep Dive')}
                </Button>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
