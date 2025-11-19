'use client';

import { useSearchParams } from 'next/navigation';

import { ActionFeed } from '@/components/v2-bi/ActionFeed';
import { GenerativeCopilot } from '@/components/v2-bi/GenerativeCopilot';
import { PerformanceHeatmap } from '@/components/v2-bi/PerformanceHeatmap';

export default function CommandCenterPage() {
  const searchParams = useSearchParams();
  const runId = searchParams.get('run_id') ?? '';
  const kpi = searchParams.get('kpi') ?? 'rto_rate';

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <ActionFeed runId={runId} />
      <PerformanceHeatmap runId={runId} kpi={kpi} />
      <GenerativeCopilot />
    </div>
  );
}
