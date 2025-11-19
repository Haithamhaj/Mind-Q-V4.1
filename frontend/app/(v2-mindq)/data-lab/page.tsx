'use client';

import { useSearchParams } from 'next/navigation';

import { AnalystGrid } from '@/components/v2-bi/AnalystGrid';
import { GenerativeCopilot } from '@/components/v2-bi/GenerativeCopilot';

export default function DataLabPage() {
  const searchParams = useSearchParams();
  const runId = searchParams.get('run_id') ?? '';

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-8">
      <AnalystGrid runId={runId} />
      <GenerativeCopilot />
    </div>
  );
}
