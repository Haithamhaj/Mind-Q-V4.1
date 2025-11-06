"use client";

import React, { useCallback } from "react";

import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

export type ChartExportColumn = {
  key: string;
  label: string;
  labelAr?: string;
  formatter?: (value: unknown, row: Record<string, unknown>) => string;
};

export type ChartExportConfig = {
  fileName?: string;
  columns: ChartExportColumn[];
  rows: Record<string, unknown>[];
  disabled?: boolean;
  label?: string;
};

const escapeCsvValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return "";
  }
  const text = String(value);
  if (text.includes('"') || text.includes(",") || text.includes("\n")) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
};

export const ChartExport: React.FC<ChartExportConfig> = ({
  fileName = "layer1-export",
  columns,
  rows,
  disabled,
  label = "Export",
}) => {
  const handleExport = useCallback(() => {
    if (!rows?.length || !columns?.length) {
      return;
    }

    const header = columns.map((column) => {
      const bilingual = column.labelAr && column.labelAr !== column.label ? `${column.label} / ${column.labelAr}` : column.label;
      return escapeCsvValue(bilingual);
    });

    const lines = rows.map((row) =>
      columns
        .map((column) => {
          const cell = column.formatter ? column.formatter(row[column.key], row) : row[column.key];
          return escapeCsvValue(cell);
        })
        .join(","),
    );

    const csvContent = [header.join(","), ...lines].join("\r\n");
    const blob = new Blob(["\ufeff" + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);

    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${fileName}.csv`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, [columns, rows, fileName]);

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="flex items-center gap-2 text-xs font-medium"
      onClick={handleExport}
      disabled={disabled || !rows?.length}
    >
      <Download className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">{label}</span>
    </Button>
  );
};
