"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Activity,
  Calendar,
  DollarSign,
  Loader2,
  MapPin,
  Package,
  RefreshCw,
  TrendingUp,
} from "lucide-react";

import { api, PipelineRunInfo } from "@/lib/api";
import { BiDashboard } from "@/components/BI/BiDashboard";
import { BiDataProvider, useBiDataContext } from "../data/provider";
import { formatCurrency, formatNumber, formatPercentage, useKpiCalculations } from "../data/kpi-calculations";

interface StoryBIDashboardProps {
  runInfo?: { runId?: string; updatedAt?: string };
}

const formatRunTimestamp = (iso?: string): string | undefined => {
  if (!iso) return undefined;
  try {
    return new Intl.DateTimeFormat("ar-SA", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
};

const StoryBIDashboard: React.FC<StoryBIDashboardProps> = ({ runInfo }) => {
  const { dataset, loading, error } = useBiDataContext();
  const kpis = useKpiCalculations(dataset);

  const formattedCount = useMemo(() => dataset.length.toLocaleString("ar-SA"), [dataset.length]);
  const kpiUpdatedAt = useMemo(
    () => formatRunTimestamp(kpis.lastUpdated ?? runInfo?.updatedAt),
    [kpis.lastUpdated, runInfo?.updatedAt],
  );
  const deliveredOrders = useMemo(() => {
    if (kpis.totalOrders !== null && kpis.slaPct !== null) {
      return Math.round(kpis.totalOrders * (kpis.slaPct / 100));
    }
    return null;
  }, [kpis.totalOrders, kpis.slaPct]);
  const formatHours = useCallback(
    (value: number | null | undefined) => {
      if (value === null || value === undefined || Number.isNaN(value)) {
        return "—";
      }
      return `${value.toFixed(1)} ساعة`;
    },
    [],
  );

  const chartMetrics = useMemo(() => {
    if (!dataset || dataset.length === 0) {
      return null;
    }

    const destinationStats = new Map<string, { count: number; codCount: number; codAmount: number }>();
    const paymentStats = new Map<string, number>();

    dataset.forEach((row) => {
      const destination =
        String((row as any)?.destination ?? (row as any)?.DESTINATION ?? "غير محدد") || "غير محدد";
      const rawPayment = String(
        (row as any)?.payment_method ??
          (row as any)?.paymentMethod ??
          (row as any)?.["RECEIVER MODE"] ??
          (row as any)?.["RECEIVER_MODE"] ??
          "",
      ).toUpperCase();
      const payment =
        rawPayment.includes("COD") ? "COD" : rawPayment.includes("CARD") ? "CC" : rawPayment || "OTHER";

      const amount = Number(
        (row as any)?.amount ??
          (row as any)?.AMOUNT ??
          (row as any)?.Shipment_Value ??
          (row as any)?.SHIPMENT_VALUE ??
          0,
      );
      const codAmount = Number((row as any)?.cod_amount ?? (row as any)?.COD_AMOUNT ?? amount ?? 0);

      const stats = destinationStats.get(destination) ?? { count: 0, codCount: 0, codAmount: 0 };
      stats.count += 1;
      if (payment === "COD") {
        stats.codCount += 1;
        stats.codAmount += codAmount;
      }
      destinationStats.set(destination, stats);

      paymentStats.set(payment, (paymentStats.get(payment) ?? 0) + 1);
    });

    const totalOrders = dataset.length;

    const ordersByDestination = [...destinationStats.entries()]
      .map(([dt, stats]) => ({ dt, val: stats.count }))
      .sort((a, b) => b.val - a.val)
      .slice(0, 10);

    const avgCodAmountDestination = [...destinationStats.entries()]
      .map(([dt, stats]) => ({
        dt,
        val: stats.codCount > 0 ? stats.codAmount / stats.codCount : 0,
      }))
      .filter((item) => item.val > 0)
      .sort((a, b) => b.val - a.val)
      .slice(0, 10);

    const codRateByDestination = [...destinationStats.entries()]
      .map(([dt, stats]) => ({
        dt,
        val: stats.count > 0 ? Number(((stats.codCount / stats.count) * 100).toFixed(2)) : 0,
      }))
      .sort((a, b) => b.val - a.val)
      .slice(0, 10);

    const codRateByReceiverMode = [...paymentStats.entries()].map(([dt, val]) => ({ dt, val }));

    return {
      orders_total: [{ dt: "total", val: totalOrders }],
      orders_by_destination: ordersByDestination,
      avg_cod_amount_destination: avgCodAmountDestination,
      cod_rate_by_receiver_mode: codRateByReceiverMode,
      cod_rate_by_destination: codRateByDestination,
    };
  }, [dataset]);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin" />
          <p className="text-muted-foreground">جارٍ تحميل بيانات لوحة BI…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="text-center">
          <Package className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="mb-2 text-lg font-semibold">تعذّر تحميل البيانات التشغيلية</h3>
          <p className="text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  if (dataset.length === 0) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <div className="text-center">
          <Package className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="mb-2 text-lg font-semibold">لا توجد بيانات متاحة</h3>
          <p className="text-muted-foreground">قم بتشغيل المرحلة العاشرة أو اختر تشغيلًا آخر.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">لوحة المعلومات التجارية الذكية</h1>
          <p className="text-muted-foreground">
            نظرة فورية على الطلبات، الدفع عند الاستلام، والبصمة التشغيلية لكل تشغيل.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {runInfo?.runId && (
            <Badge variant="outline" className="font-mono text-xs">
              {runInfo.runId}
            </Badge>
          )}
          {kpiUpdatedAt && (
            <Badge variant="secondary" className="text-xs">
              آخر تحديث: {kpiUpdatedAt}
            </Badge>
          )}
          <Badge variant="secondary" className="flex items-center gap-2 px-3 py-1 text-xs">
            <Calendar className="h-3 w-3" />
            {formattedCount} سجل
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Card className="border-primary/20 bg-gradient-to-br from-card to-primary/5 transition-all duration-300 hover:shadow-lg">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">إجمالي الطلبات</CardTitle>
            <Package className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatNumber(kpis.totalOrders)}</div>
            <div className="mt-2 space-y-1 text-xs text-muted-foreground">
              <div>آخر تحديث: {kpiUpdatedAt ?? '—'}</div>
              <div>المنطقة الزمنية: {kpis.timezone ?? 'Asia/Riyadh'}</div>
              <div>العملة: {kpis.currency ?? 'SAR'}</div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-green-500/20 bg-gradient-to-br from-card to-green-500/5 transition-all duration-300 hover:shadow-lg">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">تحصيل COD</CardTitle>
            <DollarSign className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(kpis.codTotal)}</div>
            <div className="mt-2 text-xs text-muted-foreground">متوسط تذكرة COD: {formatCurrency(kpis.codAvg)}</div>
          </CardContent>
        </Card>

        <Card className="border-orange-500/20 bg-gradient-to-br from-card to-orange-500/5 transition-all duration-300 hover:shadow-lg">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">مؤشرات الخدمة</CardTitle>
            <Activity className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatPercentage(kpis.slaPct)}</div>
            <div className="mt-2 text-xs text-muted-foreground">معدل RTO: {formatPercentage(kpis.rtoPct)}</div>
          </CardContent>
        </Card>

        <Card className="border-purple-500/20 bg-gradient-to-br from-card to-purple-500/5 transition-all duration-300 hover:shadow-lg">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">زمن التنفيذ</CardTitle>
            <MapPin className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatHours(kpis.leadTimeP50)}</div>
            <div className="mt-2 text-xs text-muted-foreground">P90: {formatHours(kpis.leadTimeP90)}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>ملخص مؤشرات التشغيل</CardTitle>
          <CardDescription>قياس سريع لأهم مؤشرات الأداء بعد المعالجة.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded-lg bg-muted/50 p-4">
              <div className="text-sm text-muted-foreground">الطلبات الموصلة تقديرًا</div>
              <div className="text-xl font-semibold">{formatNumber(deliveredOrders)}</div>
              <div className="text-xs text-green-600">من أصل {formatNumber(kpis.totalOrders)} طلب</div>
            </div>
            <div className="rounded-lg bg-muted/50 p-4">
              <div className="text-sm text-muted-foreground">معدل COD</div>
              <div className="text-xl font-semibold">{formatPercentage(kpis.codRatePct)}</div>
              <div className="text-xs text-blue-600">يعتمد على المارت التشغيلي</div>
            </div>
            <div className="rounded-lg bg-muted/50 p-4">
              <div className="text-sm text-muted-foreground">زمن التنفيذ P90</div>
              <div className="text-xl font-semibold">{formatHours(kpis.leadTimeP90)}</div>
              <div className="text-xs text-purple-600">مرجع لسقف زمن التسليم</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {chartMetrics && (
        <div className="mt-12">
          <BiDashboard
            runId={runInfo?.runId ?? ""}
            metrics={chartMetrics}
            isLoading={loading}
            showHero={false}
          />
        </div>
      )}
    </div>
  );
};

const buildRunAwareEndpoints = (runId: string) => {
  const encoded = encodeURIComponent(runId);
  return {
    dataset: `/api/bi/orders?run=${encoded}`,
    insights: `/api/bi/insights?run=${encoded}`,
    dimensions: `/api/bi/dimensions?run=${encoded}`,
  };
};

const StoryBIPage: React.FC = () => {
  const [runs, setRuns] = useState<PipelineRunInfo[]>([]);
  const [selectedRun, setSelectedRun] = useState<string>();
  const [runsLoading, setRunsLoading] = useState<boolean>(true);
  const [runsError, setRunsError] = useState<string>();
  const [refreshToken, setRefreshToken] = useState<number>(0);

  useEffect(() => {
    let mounted = true;
    const loadRuns = async () => {
      setRunsLoading(true);
      try {
        const response = await api.listRuns();
        if (!mounted) {
          return;
        }
        setRuns(response.runs);
        setRunsError(undefined);
        setSelectedRun((prev) => {
          if (prev && response.runs.some((run) => run.run_id === prev)) {
            return prev;
          }
          return response.runs[0]?.run_id ?? "run-latest";
        });
      } catch (err) {
        console.error("[story-bi] failed to load run list", err);
        if (!mounted) {
          return;
        }
        setRunsError("تعذّر تحميل قائمة التشغيلات. سيتم استخدام run-latest.");
        setSelectedRun((prev) => prev ?? "run-latest");
      } finally {
        if (mounted) {
          setRunsLoading(false);
        }
      }
    };

    loadRuns();

    return () => {
      mounted = false;
    };
  }, []);

  const runId = selectedRun ?? "run-latest";
  const providerEndpoints = useMemo(() => buildRunAwareEndpoints(runId), [runId]);
  const providerKey = useMemo(() => `${runId}-${refreshToken}`, [runId, refreshToken]);
  const runInfo = useMemo(
    () => runs.find((run) => run.run_id === runId) ?? { run_id: runId, updated_at: undefined },
    [runId, runs],
  );

  const handleRefresh = useCallback(() => {
    setRefreshToken((value) => value + 1);
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-background" dir="rtl">
      <div className="border-b border-border bg-card/50 px-6 py-5 backdrop-blur-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-foreground">اختر تشغيل المرحلة العاشرة</h2>
            <p className="text-sm text-muted-foreground">
              يتم تحميل البيانات مباشرة من مخرجات المرحلة 10 (BI Delivery) لكل تشغيل.
            </p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-3 md:w-auto">
            <div className="w-full min-w-[16rem] md:w-72">
              <Select
                value={runId}
                onValueChange={setSelectedRun}
                disabled={runsLoading || (!runs.length && !runsError)}
              >
                <SelectTrigger className="justify-between">
                  <SelectValue placeholder="اختر تشغيل BI" />
                </SelectTrigger>
                <SelectContent>
                  {runsLoading && (
                    <SelectItem value={runId} disabled>
                      جارٍ تحميل التشغيلات…
                    </SelectItem>
                  )}
                  {runs.map((run) => (
                    <SelectItem key={run.run_id} value={run.run_id}>
                      {run.run_id}
                    </SelectItem>
                  ))}
                  {!runsLoading && runs.length === 0 && (
                    <SelectItem value="run-latest">run-latest</SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="flex items-center gap-2"
              onClick={handleRefresh}
              disabled={runsLoading}
            >
              {runsLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              <span>تحديث البيانات</span>
            </Button>
          </div>
        </div>
        {runsError && <p className="mt-3 text-sm text-destructive">{runsError}</p>}
      </div>

      <div className="flex-1 bg-background">
        <BiDataProvider key={providerKey} endpoints={providerEndpoints}>
          <StoryBIDashboard runInfo={{ runId: runInfo?.run_id, updatedAt: runInfo?.updated_at }} />
        </BiDataProvider>
      </div>
    </div>
  );
};

export default StoryBIPage;
