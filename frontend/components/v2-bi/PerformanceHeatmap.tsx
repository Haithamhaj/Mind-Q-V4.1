'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false });

type HeatmapPayload = {
  x_labels: string[];
  y_labels: string[];
  data: [number, number, number][];
};

export function PerformanceHeatmap({ runId, kpi }: { runId: string; kpi: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [heatmap, setHeatmap] = useState<HeatmapPayload>({ x_labels: [], y_labels: [], data: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setHeatmap({ x_labels: [], y_labels: [], data: [] });
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ run_id: runId });
    if (kpi) {
      params.set('kpi', kpi);
    }
    fetch(`/api/v2/bi/heatmap?${params.toString()}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Heatmap error (${response.status})`);
        }
        return response.json();
      })
      .then((payload: HeatmapPayload) => {
        if (active) {
          setHeatmap(payload);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err.message);
          setHeatmap({ x_labels: [], y_labels: [], data: [] });
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
  }, [runId, kpi]);

  const maxValue = useMemo(
    () => (heatmap.data.length ? Math.max(...heatmap.data.map(([, , value]) => value)) : 1),
    [heatmap.data],
  );

  const option = useMemo(
    () => ({
      tooltip: { position: 'top' as const },
      grid: { height: '70%', top: '10%' },
      xAxis: {
        type: 'category',
        data: heatmap.x_labels,
        splitArea: { show: true },
        name: 'City',
      },
      yAxis: {
        type: 'category',
        data: heatmap.y_labels,
        splitArea: { show: true },
        name: 'Carrier',
      },
      visualMap: {
        min: 0,
        max: Math.max(maxValue, 1),
        calculable: true,
        orient: 'horizontal',
        left: 'center',
      },
      series: [
        {
          name: kpi,
          type: 'heatmap',
          data: heatmap.data,
          label: { show: true },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.4)' },
          },
        },
      ],
    }),
    [heatmap, kpi, maxValue],
  );

  const handleCellClick = (event: { data?: [number, number, number] }) => {
    if (!event?.data) return;
    const [xIdx, yIdx] = event.data;
    const city = heatmap.x_labels[xIdx];
    const carrier = heatmap.y_labels[yIdx];
    const params = new URLSearchParams(searchParams.toString());
    params.set('run_id', runId);
    if (city) params.set('city', city);
    if (carrier) params.set('carrier', carrier);
    router.push(`/data-lab?${params.toString()}`);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Performance Heatmap</CardTitle>
        <CardDescription>City x Carrier KPI view</CardDescription>
      </CardHeader>
      <CardContent>
        {loading && <p className="text-sm text-muted-foreground">Loading heatmap…</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && heatmap.data.length === 0 && (
          <p className="text-sm text-muted-foreground">No heatmap data found for this run.</p>
        )}
        {heatmap.data.length > 0 && (
          <ReactECharts option={option} style={{ height: 360 }} onEvents={{ click: handleCellClick }} />
        )}
      </CardContent>
    </Card>
  );
}
