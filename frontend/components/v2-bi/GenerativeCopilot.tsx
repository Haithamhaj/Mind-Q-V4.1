'use client';

import { useCallback, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false });

type ChartConfig = {
  type: 'bar' | 'line';
  x: string;
  y: string;
  filters: Record<string, string>;
};

type CopilotAction =
  | { kind: 'generate_chart'; payload: ChartConfig }
  | { kind: 'deep_link'; payload: Record<string, string> };

const DEFAULT_CHART_CONFIG: ChartConfig = {
  type: 'bar',
  x: 'city',
  y: 'rto_rate',
  filters: {},
};

function interpretPrompt(prompt: string): CopilotAction {
  const normalized = prompt.toLowerCase();
  const wantsChart = normalized.includes('chart') || normalized.includes('compare') || normalized.includes('trend');
  const targetCities = normalized.match(/riyadh|jeddah|dammam/gi) || [];
  if (wantsChart) {
    const filters: Record<string, string> = {};
    if (targetCities.length) {
      filters.city = targetCities.join(',');
    }
    const metric = normalized.includes('sla') ? 'sla_breach_pct' : normalized.includes('cod') ? 'cod_delay_pct' : 'rto_rate';
    return {
      kind: 'generate_chart',
      payload: {
        ...DEFAULT_CHART_CONFIG,
        x: targetCities.length > 1 ? 'city' : DEFAULT_CHART_CONFIG.x,
        y: metric,
        filters,
      },
    };
  }
  const filters: Record<string, string> = {};
  if (normalized.includes('cod')) {
    filters.payment_method = 'COD';
  }
  if (normalized.includes('failed')) {
    filters.status = 'Failed';
  }
  if (normalized.includes('sla')) {
    filters.kpi = 'sla_breach_pct';
  }
  return { kind: 'deep_link', payload: filters };
}

export function GenerativeCopilot() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [prompt, setPrompt] = useState('');
  const [action, setAction] = useState<CopilotAction | null>(null);

  const handleSubmit = useCallback(
    (event: React.FormEvent) => {
      event.preventDefault();
      if (!prompt.trim().length) {
        return;
      }
      const resolved = interpretPrompt(prompt);
      setAction(resolved);
      if (resolved.kind === 'deep_link') {
        const next = new URLSearchParams(searchParams.toString());
        Object.entries(resolved.payload).forEach(([key, value]) => {
          if (value) next.set(key, value);
        });
        router.push(`/data-lab?${next.toString()}`);
      }
    },
    [prompt, router, searchParams],
  );

  const chartOption = useMemo(() => {
    if (!action || action.kind !== 'generate_chart') {
      return null;
    }
    const { payload } = action;
    const categories = payload.filters.city ? payload.filters.city.split(',') : ['Riyadh', 'Jeddah'];
    const seriesData = categories.map((_city, idx) => Math.round((idx + 1) * 12));
    return {
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: categories, name: payload.x },
      yAxis: { type: 'value', name: payload.y },
      series: [{ name: payload.y, type: payload.type, data: seriesData }],
    };
  }, [action]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>BI Copilot</CardTitle>
        <CardDescription>Text-to-action orchestrator (URL + chart orchestration only).</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="copilot-prompt">Ask a question</Label>
            <Textarea
              id="copilot-prompt"
              value={prompt}
              placeholder="e.g. Compare SLA breach between Riyadh and Jeddah"
              onChange={(event) => setPrompt(event.target.value)}
            />
          </div>
          <div className="flex gap-3">
            <Button type="submit">Run</Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setPrompt('');
                setAction(null);
              }}
            >
              Clear
            </Button>
          </div>
        </form>
        {action?.kind === 'generate_chart' && chartOption && (
          <div className="mt-6">
            <ReactECharts option={chartOption} style={{ height: 320 }} />
          </div>
        )}
        {action?.kind === 'deep_link' && (
          <p className="mt-4 text-sm text-muted-foreground">
            Redirecting with filters: {JSON.stringify(action.payload, null, 2)}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
