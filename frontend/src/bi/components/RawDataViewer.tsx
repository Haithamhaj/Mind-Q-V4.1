"use client";

import React, { useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download, Search, SortAsc, SortDesc, Table2 } from "lucide-react";
import { ChartExport, type ChartExportColumn } from "../charts/shared/ChartExport";

export type RawDataViewerProps = {
  data: Record<string, unknown>[];
  title?: string;
  description?: string;
  maxRows?: number;
};

const formatCellValue = (value: unknown): string => {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "✓" : "✗";
  if (typeof value === "number") {
    if (Number.isInteger(value)) return value.toLocaleString("ar-SA");
    return value.toFixed(2).toLocaleString("ar-SA");
  }
  return String(value);
};

const translateColumnName = (col: string): string => {
  const translations: Record<string, string> = {
    entity_id: "رقم الكيان",
    ts: "الوقت",
    ORIGIN: "الأصل",
    DESTINATION: "الوجهة",
    RECEIVER_MODE: "طريقة الدفع",
    STATUS: "الحالة",
    COD_AMOUNT: "قيمة COD",
    kpi_orders_cnt: "عدد الطلبات",
    kpi_cod_total: "إجمالي COD",
    kpi_cod_avg: "متوسط COD",
    kpi_cod_rate: "نسبة COD",
    kpi_sla_pct: "نسبة SLA",
    decision: "القرار",
    AWB_NO: "رقم البوليصة",
    SENDER_NAME: "اسم المرسل",
    RECEIVER_NAME: "اسم المستلم",
    FORWARD_COMPANY: "شركة الشحن",
    DRIVER_NAME: "اسم السائق",
  };
  return translations[col] || col;
};

export const RawDataViewer: React.FC<RawDataViewerProps> = ({
  data,
  title = "عرض البيانات الخام",
  description = "جميع البيانات مع القدرة على الفلترة والترتيب والتصدير",
  maxRows = 100,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 50;

  // Get all columns
  const columns = useMemo(() => {
    if (!data || data.length === 0) return [];
    const allKeys = new Set<string>();
    data.forEach((row) => {
      Object.keys(row).forEach((key) => allKeys.add(key));
    });
    return Array.from(allKeys);
  }, [data]);

  // Filter and sort data
  const processedData = useMemo(() => {
    let result = [...data];

    // Search filter
    if (searchTerm) {
      const lowerSearch = searchTerm.toLowerCase();
      result = result.filter((row) =>
        Object.values(row).some((value) =>
          String(value).toLowerCase().includes(lowerSearch)
        )
      );
    }

    // Sort
    if (sortColumn) {
      result.sort((a, b) => {
        const aVal = a[sortColumn];
        const bVal = b[sortColumn];
        
        if (aVal === null || aVal === undefined) return 1;
        if (bVal === null || bVal === undefined) return -1;
        
        if (typeof aVal === "number" && typeof bVal === "number") {
          return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
        }
        
        const aStr = String(aVal);
        const bStr = String(bVal);
        return sortDirection === "asc"
          ? aStr.localeCompare(bStr)
          : bStr.localeCompare(aStr);
      });
    }

    return result;
  }, [data, searchTerm, sortColumn, sortDirection]);

  // Pagination
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * rowsPerPage;
    const end = start + rowsPerPage;
    return processedData.slice(start, end);
  }, [processedData, currentPage]);

  const totalPages = Math.ceil(processedData.length / rowsPerPage);

  // Export config
  const exportColumns: ChartExportColumn[] = columns.map((col) => ({
    key: col,
    label: col,
    labelAr: translateColumnName(col),
  }));

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortColumn(column);
      setSortDirection("asc");
    }
  };

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Table2 className="h-5 w-5" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">لا توجد بيانات متاحة</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Table2 className="h-5 w-5" />
              {title}
            </CardTitle>
            <CardDescription>
              {description} • {processedData.length.toLocaleString("ar-SA")} صف
            </CardDescription>
          </div>
          <ChartExport
            fileName="raw-data-export"
            columns={exportColumns}
            rows={processedData}
            label="تصدير"
          />
        </div>
      </CardHeader>
      <CardContent>
        {/* Search and filters */}
        <div className="mb-4 flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="بحث في البيانات..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className="pl-10"
            />
          </div>
          <Select value={sortColumn || ""} onValueChange={(value) => handleSort(value)}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="ترتيب حسب..." />
            </SelectTrigger>
            <SelectContent>
              {columns.slice(0, 20).map((col) => (
                <SelectItem key={col} value={col}>
                  {translateColumnName(col)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                {columns.slice(0, 15).map((col) => (
                  <th
                    key={col}
                    className="cursor-pointer border-b px-4 py-3 text-right font-medium transition-colors hover:bg-muted"
                    onClick={() => handleSort(col)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate">{translateColumnName(col)}</span>
                      {sortColumn === col && (
                        sortDirection === "asc" ? (
                          <SortAsc className="h-4 w-4" />
                        ) : (
                          <SortDesc className="h-4 w-4" />
                        )
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginatedData.map((row, idx) => (
                <tr key={idx} className="border-b transition-colors hover:bg-muted/30">
                  {columns.slice(0, 15).map((col) => (
                    <td key={col} className="px-4 py-3 text-right">
                      {formatCellValue(row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              صفحة {currentPage} من {totalPages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                السابق
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                التالي
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
