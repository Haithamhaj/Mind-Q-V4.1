"use client";

import dynamic from "next/dynamic";

const EnhancedStoryBIPage = dynamic(
  () => import("../../src/bi/pages/EnhancedStoryBIPage"),
  {
    loading: () => (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-b-2 border-primary" />
          <p className="text-muted-foreground">يتم تحميل لوحة المعلومات الذكية...</p>
        </div>
      </div>
    ),
  },
);

export default function BiIntelligencePage() {
  return <EnhancedStoryBIPage />;
}
