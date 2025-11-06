"use client"

import React, { useEffect, useRef } from 'react';

import * as echarts from 'echarts';

import type { EChartsType } from 'echarts';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { Badge } from "@/components/ui/badge";

import { Button } from "@/components/ui/button";

import { 

  TrendingUp, 

  Package, 

  DollarSign, 

  MapPin, 

  Calendar,

  BarChart3,

  LineChart,

  PieChart,

  Activity,

  Loader2,

  ArrowUpRight,

  ArrowDownRight

} from "lucide-react";

interface BiDashboardProps {

  runId: string;

  metrics: any;

  isLoading: boolean;

  showHero?: boolean;

}

export function BiDashboard({ runId, metrics, isLoading, showHero = true }: BiDashboardProps) {

  const ordersChartRef = useRef<HTMLDivElement>(null);

  const codAmountChartRef = useRef<HTMLDivElement>(null);

  const codRateChartRef = useRef<HTMLDivElement>(null);

  const trendsChartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!metrics || Object.keys(metrics).length === 0 || isLoading) {
      return;
    }

    const charts = initializeCharts(metrics);

    const handleResize = () => {
      charts.forEach((chart) => {
        if (!chart.isDisposed()) {
          chart.resize();
        }
      });
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      charts.forEach((chart) => {
        if (!chart.isDisposed()) {
          chart.dispose();
        }
      });
    };
  }, [metrics, isLoading]);

  const initializeCharts = (data: any): EChartsType[] => {
    const chartInstances: EChartsType[] = [];

    const ensureInstance = (target: HTMLDivElement | null) => {
      if (!target) {
        return null;
      }

      const existing = echarts.getInstanceByDom(target);
      if (existing) {
        existing.clear();
        return existing;
      }

      return echarts.init(target, undefined, { renderer: 'svg' });
    };

    const axisStyling = {
      axisLabel: { fontSize: 11, color: '#e2e8f0' },
      axisLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.35)' } },
      splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.12)' } },
    };

    if (ordersChartRef.current && data.orders_by_destination?.length > 0) {
      const chart = ensureInstance(ordersChartRef.current);
      if (chart) {
        chart.setOption({
          backgroundColor: 'transparent',
          tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: 'rgba(15, 23, 42, 0.85)',
            borderColor: 'rgba(148, 163, 184, 0.35)',
            textStyle: { color: '#f8fafc' },
          },
          xAxis: {
            type: 'category',
            data: data.orders_by_destination.map((item: any) => item.dt),
            axisLabel: { rotate: 45, fontSize: 11, color: '#e2e8f0' },
            axisLine: axisStyling.axisLine,
          },
          yAxis: {
            type: 'value',
            axisLabel: axisStyling.axisLabel,
            axisLine: axisStyling.axisLine,
            splitLine: axisStyling.splitLine,
          },
          series: [{
            name: 'عدد الطلبات',
            type: 'bar',
            data: data.orders_by_destination.map((item: any) => item.val),
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#3b82f6' },
                { offset: 1, color: '#1e40af' },
              ]),
            },
            emphasis: {
              itemStyle: { color: '#2563eb' },
            },
          }],
          grid: { left: '3%', right: '4%', bottom: '18%', top: '10%', containLabel: true },
          animation: true,
          animationDuration: 1000,
        });
        chart.resize();
        chartInstances.push(chart);
      }
    }

    if (codAmountChartRef.current && data.avg_cod_amount_destination?.length > 0) {
      const chart = ensureInstance(codAmountChartRef.current);
      if (chart) {
        chart.setOption({
          backgroundColor: 'transparent',
          tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(15, 23, 42, 0.85)',
            borderColor: 'rgba(148, 163, 184, 0.35)',
            textStyle: { color: '#f8fafc' },
          },
          xAxis: {
            type: 'category',
            data: data.avg_cod_amount_destination.map((item: any) => item.dt),
            axisLabel: { rotate: 45, fontSize: 11, color: '#e2e8f0' },
            axisLine: axisStyling.axisLine,
          },
          yAxis: {
            type: 'value',
            axisLabel: axisStyling.axisLabel,
            axisLine: axisStyling.axisLine,
            splitLine: axisStyling.splitLine,
          },
          series: [{
            name: 'متوسط مبلغ الدفع عند الاستلام',
            type: 'bar',
            data: data.avg_cod_amount_destination.map((item: any) => item.val),
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#10b981' },
                { offset: 1, color: '#059669' },
              ]),
            },
          }],
          grid: { left: '3%', right: '4%', bottom: '18%', top: '10%', containLabel: true },
          animation: true,
          animationDuration: 1200,
        });
        chart.resize();
        chartInstances.push(chart);
      }
    }

    if (codRateChartRef.current && data.cod_rate_by_receiver_mode?.length > 0) {
      const chart = ensureInstance(codRateChartRef.current);
      if (chart) {
        chart.setOption({
          backgroundColor: 'transparent',
          tooltip: {
            trigger: 'item',
            formatter: '{a} <br/>{b}: {c} ({d}%)',
          },
          legend: {
            orient: 'vertical',
            left: 'left',
            textStyle: { fontSize: 11, color: '#e2e8f0' },
          },
          series: [{
            name: 'طريقة الدفع',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            data: data.cod_rate_by_receiver_mode.map((item: any) => ({
              value: item.val,
              name: item.dt === 'COD' ? 'الدفع عند الاستلام' : 'الدفع بالبطاقة',
            })),
            itemStyle: {
              borderRadius: 10,
              borderColor: '#0f172a',
              borderWidth: 2,
            },
            label: {
              show: false,
              position: 'center',
            },
            emphasis: {
              label: {
                show: true,
                fontSize: 20,
                fontWeight: 'bold',
              },
            },
            labelLine: {
              show: false,
            },
          }],
          color: ['#f59e0b', '#3b82f6'],
          animation: true,
          animationDuration: 1500,
        });
        chart.resize();
        chartInstances.push(chart);
      }
    }

    if (trendsChartRef.current && data.cod_rate_by_destination?.length > 0) {
      const chart = ensureInstance(trendsChartRef.current);
      if (chart) {
        chart.setOption({
          backgroundColor: 'transparent',
          tooltip: {
            trigger: 'axis',
            formatter: (params: any) => `${params[0].name}<br/>معدل الدفع عند الاستلام: ${(params[0].value * 100).toFixed(1)}%`,
          },
          xAxis: {
            type: 'category',
            data: data.cod_rate_by_destination.map((item: any) => item.dt),
            axisLabel: { rotate: 45, fontSize: 11, color: '#e2e8f0' },
            axisLine: axisStyling.axisLine,
          },
          yAxis: {
            type: 'value',
            axisLabel: {
              fontSize: 11,
              color: '#e2e8f0',
              formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
            },
            axisLine: axisStyling.axisLine,
            splitLine: axisStyling.splitLine,
          },
          series: [{
            name: 'معدل الدفع عند الاستلام',
            type: 'line',
            data: data.cod_rate_by_destination.map((item: any) => item.val),
            smooth: true,
            lineStyle: { width: 3, color: '#8b5cf6' },
            itemStyle: { color: '#8b5cf6' },
            areaStyle: {
              opacity: 0.3,
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#8b5cf6' },
                { offset: 1, color: 'transparent' },
              ]),
            },
          }],
          grid: { left: '3%', right: '4%', bottom: '18%', top: '10%', containLabel: true },
          animation: true,
          animationDuration: 1000,
        });
        chart.resize();
        chartInstances.push(chart);
      }
    }

    return chartInstances;
  };

  // Calculate metrics with corrected data

  const totalOrders = metrics?.orders_total?.[0]?.val ?? 0;

  const totalDestinations = metrics?.orders_by_destination?.length ?? 0;

  const codOrders = metrics?.cod_rate_by_receiver_mode?.find((item: any) => item.dt === 'COD')?.val ?? 0;

  const ccOrders = metrics?.cod_rate_by_receiver_mode?.find((item: any) => item.dt === 'CC')?.val ?? 0;

  const codRate = totalOrders > 0 ? (codOrders / totalOrders * 100) : 0;

  const topDestination = metrics?.orders_by_destination?.[0] ?? null;

  return (

    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 relative overflow-hidden">
      {/* Animated background */}
      <div className="absolute inset-0 bg-[url('/api/placeholder/100/100')] opacity-5"></div>
      <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 via-blue-500/5 to-emerald-500/10 animate-pulse"></div>
      
      <div className="relative z-10 mx-auto max-w-7xl p-6">

        {showHero && (
          <>
        {/* Modern Header with Glass Effect */}
        <div className="mb-12 text-center relative">
          <div className="absolute inset-0 bg-white/10 backdrop-blur-lg rounded-3xl border border-white/20 shadow-2xl"></div>
          <div className="relative p-8">
            <div className="flex justify-center mb-4">
              <div className="p-4 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full shadow-2xl">
                <Activity className="h-8 w-8 text-white animate-pulse" />
              </div>
            </div>
            <h1 className="mb-4 text-5xl font-extrabold bg-gradient-to-r from-blue-400 via-purple-400 to-emerald-400 bg-clip-text text-transparent">
              🚀 لوحة المعلومات التجارية المتطورة
            </h1>
            <p className="text-xl text-gray-300 font-light">
              ✨ تحليل ذكي متقدم مع رؤى فورية ومؤشرات تفاعلية
            </p>
            <Badge className="mt-4 bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-xl border-0 px-6 py-2 text-lg">
              <Activity className="mr-2 h-5 w-5 animate-spin" />
              🎯 معرف التشغيل: {runId}
            </Badge>
          </div>
        </div>

        {/* Advanced KPI Cards with Glass Morphism */}
        <div className="mb-12 grid gap-8 md:grid-cols-2 lg:grid-cols-4">
          
          <Card className="group relative border-0 bg-white/5 backdrop-blur-xl shadow-2xl hover:shadow-blue-500/25 transition-all duration-500 hover:scale-105 hover:bg-white/10">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/20 to-cyan-500/20 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            <CardHeader className="relative z-10 flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-semibold text-white/90">📦 إجمالي الطلبات</CardTitle>
              <div className="p-3 bg-gradient-to-r from-blue-500 to-cyan-500 rounded-xl shadow-lg">
                <Package className="h-6 w-6 text-white animate-bounce" />
              </div>
            </CardHeader>
            <CardContent className="relative z-10">
              <div className="text-4xl font-black text-white mb-2">{totalOrders.toLocaleString()}</div>
              <p className="text-sm text-blue-300 flex items-center">
                <ArrowUpRight className="inline h-4 w-4 mr-1 animate-pulse" />
                العدد الإجمالي للطلبات المسجلة
              </p>
            </CardContent>
          </Card>

          <Card className="group relative border-0 bg-white/5 backdrop-blur-xl shadow-2xl hover:shadow-emerald-500/25 transition-all duration-500 hover:scale-105 hover:bg-white/10">
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/20 to-green-500/20 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            <CardHeader className="relative z-10 flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-semibold text-white/90">💳 معدل الدفع عند الاستلام</CardTitle>
              <div className="p-3 bg-gradient-to-r from-emerald-500 to-green-500 rounded-xl shadow-lg">
                <DollarSign className="h-6 w-6 text-white animate-pulse" />
              </div>
            </CardHeader>
            <CardContent className="relative z-10">
              <div className="text-4xl font-black text-white mb-2">{codRate.toFixed(1)}%</div>
              <p className="text-sm text-emerald-300">
                🎯 {codOrders.toLocaleString()} من أصل {totalOrders.toLocaleString()} طلب
              </p>
            </CardContent>
          </Card>

          <Card className="group relative border-0 bg-white/5 backdrop-blur-xl shadow-2xl hover:shadow-purple-500/25 transition-all duration-500 hover:scale-105 hover:bg-white/10">
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            <CardHeader className="relative z-10 flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-semibold text-white/90">🗺️ عدد الوجهات</CardTitle>
              <div className="p-3 bg-gradient-to-r from-purple-500 to-pink-500 rounded-xl shadow-lg">
                <MapPin className="h-6 w-6 text-white animate-spin" />
              </div>
            </CardHeader>
            <CardContent className="relative z-10">
              <div className="text-4xl font-black text-white mb-2">{totalDestinations}</div>
              <p className="text-sm text-purple-300">
                🌍 المناطق الجغرافية المختلفة
              </p>
            </CardContent>
          </Card>

          <Card className="group relative border-0 bg-white/5 backdrop-blur-xl shadow-2xl hover:shadow-amber-500/25 transition-all duration-500 hover:scale-105 hover:bg-white/10">
            <div className="absolute inset-0 bg-gradient-to-br from-amber-500/20 to-orange-500/20 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            <CardHeader className="relative z-10 flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-semibold text-white/90">🏆 أكبر وجهة</CardTitle>
              <div className="p-3 bg-gradient-to-r from-amber-500 to-orange-500 rounded-xl shadow-lg">
                <TrendingUp className="h-6 w-6 text-white animate-bounce" />
              </div>
            </CardHeader>
            <CardContent className="relative z-10">
              <div className="text-3xl font-black text-white mb-2">
                {topDestination?.dt || 'غير محدد'}
              </div>
              <p className="text-sm text-amber-300">
                📈 {topDestination?.val?.toLocaleString() || 0} طلب
              </p>
            </CardContent>
          </Card>

        </div>
          </>
        )}
        {/* Modern Charts Section with Futuristic Tabs */}
        <Tabs defaultValue="geographic" className="space-y-8">
          
          <TabsList className="grid w-full grid-cols-4 bg-white/5 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl p-2">
            <TabsTrigger 
              value="geographic" 
              className="flex items-center gap-3 bg-transparent data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-500 data-[state=active]:to-cyan-500 data-[state=active]:text-white text-white/70 border-0 rounded-xl transition-all duration-300 hover:bg-white/10 py-3"
            >
              <MapPin className="h-5 w-5" />
              🗺️ التوزيع الجغرافي
            </TabsTrigger>
            <TabsTrigger 
              value="payment" 
              className="flex items-center gap-3 bg-transparent data-[state=active]:bg-gradient-to-r data-[state=active]:from-emerald-500 data-[state=active]:to-green-500 data-[state=active]:text-white text-white/70 border-0 rounded-xl transition-all duration-300 hover:bg-white/10 py-3"
            >
              <PieChart className="h-5 w-5" />
              💳 طرق الدفع
            </TabsTrigger>
            <TabsTrigger 
              value="amounts" 
              className="flex items-center gap-3 bg-transparent data-[state=active]:bg-gradient-to-r data-[state=active]:from-purple-500 data-[state=active]:to-pink-500 data-[state=active]:text-white text-white/70 border-0 rounded-xl transition-all duration-300 hover:bg-white/10 py-3"
            >
              <BarChart3 className="h-5 w-5" />
              📊 المبالغ
            </TabsTrigger>
            <TabsTrigger 
              value="trends" 
              className="flex items-center gap-3 bg-transparent data-[state=active]:bg-gradient-to-r data-[state=active]:from-amber-500 data-[state=active]:to-orange-500 data-[state=active]:text-white text-white/70 border-0 rounded-xl transition-all duration-300 hover:bg-white/10 py-3"
            >
              <LineChart className="h-5 w-5" />
              📈 الاتجاهات
            </TabsTrigger>
          </TabsList>

          <TabsContent value="geographic">
            <Card className="border-0 bg-white/5 backdrop-blur-xl shadow-2xl">
              <CardHeader className="pb-6">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-3 text-2xl font-bold text-white">
                    <div className="p-2 bg-gradient-to-r from-blue-500 to-cyan-500 rounded-lg">
                      <MapPin className="h-6 w-6 text-white" />
                    </div>
                    🗺️ توزيع الطلبات حسب الوجهة الجغرافية
                  </CardTitle>
                  <Badge className="bg-gradient-to-r from-blue-500 to-cyan-500 text-white border-0">
                    تحديث مباشر ⚡
                  </Badge>
                </div>
                <CardDescription className="text-blue-200 text-lg mt-2">
                  ✨ عرض توزيع الطلبات على المناطق المختلفة في المملكة العربية السعودية
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="p-4 bg-gradient-to-br from-blue-500/10 to-cyan-500/10 rounded-2xl border border-white/10">
                  <div ref={ordersChartRef} className="h-96 w-full" />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="payment">
            <Card className="border-0 bg-white/5 backdrop-blur-xl shadow-2xl">
              <CardHeader className="pb-6">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-3 text-2xl font-bold text-white">
                    <div className="p-2 bg-gradient-to-r from-emerald-500 to-green-500 rounded-lg">
                      <PieChart className="h-6 w-6 text-white" />
                    </div>
                    💳 توزيع طرق الدفع
                  </CardTitle>
                  <Badge className="bg-gradient-to-r from-emerald-500 to-green-500 text-white border-0">
                    تحليل ذكي 🧠
                  </Badge>
                </div>
                <CardDescription className="text-emerald-200 text-lg mt-2">
                  📊 مقارنة بين الدفع عند الاستلام والدفع بالبطاقة الائتمانية
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="p-4 bg-gradient-to-br from-emerald-500/10 to-green-500/10 rounded-2xl border border-white/10">
                  <div ref={codRateChartRef} className="h-96 w-full" />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="amounts">
            <Card className="border-0 bg-white/5 backdrop-blur-xl shadow-2xl">
              <CardHeader className="pb-6">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-3 text-2xl font-bold text-white">
                    <div className="p-2 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg">
                      <BarChart3 className="h-6 w-6 text-white" />
                    </div>
                    💰 متوسط مبالغ الدفع عند الاستلام حسب الوجهة
                  </CardTitle>
                  <Badge className="bg-gradient-to-r from-purple-500 to-pink-500 text-white border-0">
                    رؤى مالية 💎
                  </Badge>
                </div>
                <CardDescription className="text-purple-200 text-lg mt-2">
                  📈 تحليل متوسط المبالغ المدفوعة عند الاستلام في كل منطقة
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="p-4 bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-2xl border border-white/10">
                  <div ref={codAmountChartRef} className="h-96 w-full" />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="trends">
            <Card className="border-0 bg-white/5 backdrop-blur-xl shadow-2xl">
              <CardHeader className="pb-6">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-3 text-2xl font-bold text-white">
                    <div className="p-2 bg-gradient-to-r from-amber-500 to-orange-500 rounded-lg">
                      <LineChart className="h-6 w-6 text-white" />
                    </div>
                    📊 معدل الدفع عند الاستلام حسب المنطقة
                  </CardTitle>
                  <Badge className="bg-gradient-to-r from-amber-500 to-orange-500 text-white border-0">
                    اتجاهات متقدمة 🚀
                  </Badge>
                </div>
                <CardDescription className="text-amber-200 text-lg mt-2">
                  🔍 تحليل اتجاهات استخدام الدفع عند الاستلام في المناطق المختلفة
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="p-4 bg-gradient-to-br from-amber-500/10 to-orange-500/10 rounded-2xl border border-white/10">
                  <div ref={trendsChartRef} className="h-96 w-full" />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

        </Tabs>

        {/* Futuristic Footer */}
        <div className="mt-12 text-center">
          <div className="flex justify-center gap-6 mb-8">
            <Button className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white border-0 shadow-2xl px-8 py-4 text-lg rounded-2xl transition-all duration-300 hover:scale-105">
              <Calendar className="mr-3 h-6 w-6 animate-pulse" />
              🔄 تحديث البيانات
            </Button>
            <Button className="bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-600 hover:to-green-600 text-white border-0 shadow-2xl px-8 py-4 text-lg rounded-2xl transition-all duration-300 hover:scale-105">
              📊 تصدير التقرير المتقدم
            </Button>
          </div>
          
          {/* Status Indicator */}
          <div className="flex justify-center items-center gap-3 text-white/60">
            <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse shadow-lg shadow-green-400/50"></div>
            <span className="text-sm font-medium">متصل ومحدث</span>
            <div className="text-xs">⚡ {new Date().toLocaleString('ar-SA')}</div>
          </div>
        </div>

      </div>

    </div>

  );

}


