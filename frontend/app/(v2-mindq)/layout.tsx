import type { ReactNode } from 'react';

import { GlobalFilterBar } from '@/components/v2-bi/GlobalFilterBar';

export default function MindQV2Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <GlobalFilterBar />
      <main className="flex-1 bg-muted/20">{children}</main>
    </div>
  );
}
