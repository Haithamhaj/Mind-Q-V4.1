"use client";

import React, { useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Database, Download, TrendingDown, ZoomIn } from "lucide-react";

import { BiDataProvider, useFilteredDataset, useBiDimensions } from "../data";
import { RawDataViewer, AdvancedExport, DrillDownPanel, type DrillDownData } from "../components";
import { FilterBar } from "../components/FilterBar";

const RawDataDashboard: React.FC = () => {
  const dataset = useFilteredDataset() || [];
  const dimensions = useBiDimensions();

  // Build export columns from dataset
  const exportColumns = useMemo(() => {
    if (!dataset || dataset.length === 0) return [];
    const firstRow = dataset[0];
    if (!firstRow) return [];
    return Object.keys(firstRow).map((key) => ({
      key,
      label: key,
      labelAr: key, // Could add translations here
    }));
  }, [dataset]);

  // Build drill-down data from dataset (example: by DESTINATION)
  const drillDownData: DrillDownData[] = useMemo(() => {
    if (!dataset || dataset.length === 0) return [];

    const destinationGroups = new Map<string, { count: number; cod: number }>();
    
    dataset.forEach((row: any) => {
      if (!row) return;
      const dest = String(row.DESTINATION || row.destination || "Unknown");
      const existing = destinationGroups.get(dest) || { count: 0, cod: 0 };
      existing.count += 1;
      if (row.COD_AMOUNT) existing.cod += Number(row.COD_AMOUNT) || 0;
      destinationGroups.set(dest, existing);
    });

    const total = dataset.length;
    if (total === 0) return [];
    
    return Array.from(destinationGroups.entries())
      .map(([value, stats]) => ({
        value,
        label: value,
        count: stats.count,
        percentage: (stats.count / total) * 100,
        metric: stats.count > 0 ? stats.cod / stats.count : 0,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 20);
  }, [dataset]);

  return (
    <div className="container mx-auto space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">البيانات الخام والتحليل التفصيلي</h1>
          <p className="text-muted-foreground">
            استكشف البيانات الكاملة مع إمكانيات الفلترة والتصدير والتحليل التفصيلي
          </p>
        </div>
        <AdvancedExport
          fileName="mind-q-raw-data"
          reportTitle="Mind-Q Raw Data Report"
          reportTitleAr="تقرير البيانات الخام - Mind-Q"
          columns={exportColumns}
          rows={dataset}
        />
      </div>

      {/* Filter Bar */}
      <FilterBar />

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">إجمالي السجلات</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dataset.length.toLocaleString("ar-SA")}</div>
            <p className="text-xs text-muted-foreground">سجل متاح للتحليل</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">الأعمدة المتاحة</CardTitle>
            <TrendingDown className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{exportColumns.length}</div>
            <p className="text-xs text-muted-foreground">حقل بيانات</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">أبعاد التحليل</CardTitle>
            <ZoomIn className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(dimensions?.categorical?.length || 0) + (dimensions?.temporal?.length || 0)}
            </div>
            <p className="text-xs text-muted-foreground">بُعد تصنيفي وزمني</p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs for different views */}
      <Tabs defaultValue="table" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="table">جدول البيانات</TabsTrigger>
          <TabsTrigger value="drilldown">التحليل التفصيلي</TabsTrigger>
        </TabsList>

        <TabsContent value="table" className="mt-6">
          <RawDataViewer
            data={dataset}
            title="جدول البيانات الكامل"
            description="جميع البيانات المتاحة مع إمكانيات البحث والفلترة والترتيب"
            maxRows={1000}
          />
        </TabsContent>

        <TabsContent value="drilldown" className="mt-6">
          <DrillDownPanel
            title="تحليل تفصيلي حسب الوجهة"
            data={drillDownData}
            maxLevels={3}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};

const RawDataPage: React.FC = () => {
  return (
    <BiDataProvider>
      <RawDataDashboard />
    </BiDataProvider>
  );
};

export default RawDataPage;
