"use client";

import React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { BarChart3, Database } from "lucide-react";

export const BiNavigation: React.FC = () => {
  return (
    <div className="flex items-center gap-2">
      <Link href="/bi">
        <Button variant="ghost" size="sm" className="gap-2">
          <BarChart3 className="h-4 w-4" />
          <span className="hidden sm:inline">لوحة التحليلات</span>
        </Button>
      </Link>
      <Link href="/bi-raw">
        <Button variant="ghost" size="sm" className="gap-2">
          <Database className="h-4 w-4" />
          <span className="hidden sm:inline">البيانات الخام</span>
        </Button>
      </Link>
    </div>
  );
};
