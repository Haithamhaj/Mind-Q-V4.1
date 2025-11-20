'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useLanguage } from '@/context/language-context';

const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false });

type HeatmapPayload = {
  x_labels: string[];
  y_labels: string[];
  data: [number, number, number][];
};

type LimitedHeatmap = HeatmapPayload & { truncated: boolean };

const MAX_CITIES = 18;
const MAX_CARRIERS = 12;

const aggregateTopLabels = (
  labels: string[],
  data: [number, number, number][],
  axis: 'x' | 'y',
  limit: number,
) => {
  if (!labels.length) {
    return [];
  }
  const score: Record<string, number> = {};
  data.forEach(([xIdx, yIdx, value]) => {
    const idx = axis === 'x' ? xIdx : yIdx;
    const label = labels[idx];
    if (label === undefined) {
      return;
    }
    const contribution = Number.isFinite(value) ? Math.abs(value) : 0;
    score[label] = (score[label] ?? 0) + contribution;
  });
  const entries = Object.entries(score);
  if (!entries.length) {
    return labels.slice(0, limit);
  }
  return entries
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([label]) => label);
};

const remapDataset = (payload: HeatmapPayload): LimitedHeatmap => {
  if (!payload.x_labels.length || !payload.y_labels.length) {
    return { ...payload, truncated: false };
  }
  const selectedCities = aggregateTopLabels(payload.x_labels, payload.data, 'x', MAX_CITIES);
  const selectedCarriers = aggregateTopLabels(payload.y_labels, payload.data, 'y', MAX_CARRIERS);
  const cityMap = new Map(selectedCities.map((label, idx) => [label, idx]));
  const carrierMap = new Map(selectedCarriers.map((label, idx) => [label, idx]));
  const filtered: [number, number, number][] = [];
  payload.data.forEach(([xIdx, yIdx, value]) => {
    const city = payload.x_labels[xIdx];
    const carrier = payload.y_labels[yIdx];
    if (!cityMap.has(city) || !carrierMap.has(carrier)) {
      return;
    }
    filtered.push([cityMap.get(city)!, carrierMap.get(carrier)!, value]);
  });
  return {
    x_labels: selectedCities,
    y_labels: selectedCarriers,
    data: filtered,
    truncated:
      selectedCities.length < payload.x_labels.length || selectedCarriers.length < payload.y_labels.length,
  };
};

export function PerformanceHeatmap({ runId, kpi }: { runId: string; kpi: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { translate, language } = useLanguage();
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
          throw new Error(`${translate('Heatmap error')} (${response.status})`);
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
  }, [runId, kpi, translate]);

  const limited = useMemo(() => remapDataset(heatmap), [heatmap]);
  const maxValue = useMemo(
    () => (limited.data.length ? Math.max(...limited.data.map(([, , value]) => value ?? 0)) : 1),
    [limited.data],
  );
  const isArabic = language === 'ar';
  const rotation = isArabic ? 25 : -35;
  const truncatedNote = limited.truncated
    ? translate('Showing top {cities} cities × {carriers} carriers', {
        cities: limited.x_labels.length,
        carriers: limited.y_labels.length,
      })
    : null;
  const chartWidth = Math.max(680, limited.x_labels.length * 70);

  const option = useMemo(
    () => ({
      tooltip: {
        formatter: (params: { value?: [number, number, number] }) => {
          if (!params?.value) {
            return '';
          }
          const [xIdx, yIdx, value] = params.value;
          const city = limited.x_labels[xIdx] ?? '';
          const carrier = limited.y_labels[yIdx] ?? '';
          return `${city} × ${carrier}: ${Number(value ?? 0).toFixed(3)}`;
        },
      },
      grid: { top: 50, bottom: 90, left: 120, right: 40 },
      xAxis: {
        type: 'category',
        data: limited.x_labels,
        splitArea: { show: true },
        axisLabel: { rotate: rotation, fontSize: 12 },
        name: translate('City'),
        nameLocation: 'middle',
        nameGap: 50,
      },
      yAxis: {
        type: 'category',
        data: limited.y_labels,
        splitArea: { show: true },
        axisLabel: { fontSize: 12 },
        name: translate('Carrier'),
        nameLocation: 'middle',
        nameGap: 50,
      },
      visualMap: {
        min: 0,
        max: Math.max(maxValue, 0.25),
        calculable: true,
        orient: 'vertical',
        left: isArabic ? 'auto' : 10,
        right: isArabic ? 10 : 'auto',
        top: 20,
      },
      series: [
        {
          name: kpi,
          type: 'heatmap',
          data: limited.data,
          label: {
            show: limited.y_labels.length <= 12,
            fontSize: 10,
            formatter: ({ value }: { value?: [number, number, number] }) =>
              value ? Number(value[2] ?? 0).toFixed(2) : '',
          },
          emphasis: {
            itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.4)' },
          },
        },
      ],
    }),
    [limited, kpi, translate, rotation, isArabic, maxValue],
  );

  const handleCellClick = (event: { data?: [number, number, number] }) => {
    if (!event?.data) return;
    const [xIdx, yIdx] = event.data;
    const city = limited.x_labels[xIdx];
    const carrier = limited.y_labels[yIdx];
    const params = new URLSearchParams(searchParams.toString());
    params.set('run_id', runId);
    if (city) params.set('city', city);
    if (carrier) params.set('carrier', carrier);
    router.push(`/data-lab?${params.toString()}`);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{translate('Performance Heatmap')}</CardTitle>
        <CardDescription>{translate('City x Carrier KPI view')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {truncatedNote && (
          <p className="text-muted-foreground">{translate('Heatmap filtered for readability')}</p>
        )}
        {loading && <p className="text-sm text-muted-foreground">{translate('Loading heatmap…')}</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!loading && limited.data.length === 0 && (
          <p className="text-sm text-muted-foreground">{translate('No heatmap data found for this run.')}</p>
        )}
        {!loading && limited.data.length > 0 && (
          <>
            {truncatedNote && <p className="text-xs text-muted-foreground">{truncatedNote}</p>}
            <div className="w-full overflow-x-auto">
              <ReactECharts
                option={option}
                style={{ height: 420, width: chartWidth }}
                onEvents={{ click: handleCellClick }}
              />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
