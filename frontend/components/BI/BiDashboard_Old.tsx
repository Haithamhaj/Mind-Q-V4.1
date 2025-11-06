"use client"

import React, { useCallback, useEffect, useRef } from 'react';
import * as echarts from 'echarts';
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
}

export function BiDashboard({ runId, metrics, isLoading }: BiDashboardProps) {
  const ordersChartRef = useRef<HTMLDivElement>(null);
  const codAmountChartRef = useRef<HTMLDivElement>(null);
  const codRateChartRef = useRef<HTMLDivElement>(null);
  const trendsChartRef = useRef<HTMLDivElement>(null);

  const initializeCharts = useCallback((data: any) => {
    // Orders by Destination Chart (replacing daily orders with geographic data)
    if (ordersChartRef.current && data.orders_by_destination?.length > 0) {
      const chart = echarts.init(ordersChartRef.current);
      chart.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          borderColor: '#333',
          textStyle: { color: '#fff' }
        },
        xAxis: {
          type: 'category',
          data: data.orders_by_destination.map((item: any) => item.dt),
          axisLabel: { rotate: 45, fontSize: 10 }
        },
        yAxis: { 
          type: 'value',
          axisLabel: { fontSize: 10 }
        },
        series: [{
          name: 'عدد الطلبات',
          type: 'bar',
          data: data.orders_by_destination.map((item: any) => item.val),
          itemStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#3b82f6' },
              { offset: 1, color: '#1e40af' }
            ])
          },
          emphasis: {
            itemStyle: {
              color: '#2563eb'
            }
          }
        }],
        grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
        animation: true,
        animationDuration: 1000
      });
    }

    // COD Amount Chart
    if (codAmountChartRef.current && data.avg_cod_amount_destination?.length > 0) {
      const chart = echarts.init(codAmountChartRef.current);
      chart.setOption({
        tooltip: { 
          trigger: 'axis',
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          borderColor: '#333',
          textStyle: { color: '#fff' }
        },
        xAxis: {
          type: 'category',
          data: data.avg_cod_amount_destination.map((item: any) => item.dt),
          axisLabel: { rotate: 45, fontSize: 10 }
        },
        yAxis: { 
          type: 'value',
          axisLabel: { fontSize: 10 }
        },
        series: [{
          name: 'متوسط مبلغ الدفع عند الاستلام',
          type: 'bar',
          data: data.avg_cod_amount_destination.map((item: any) => item.val),
          itemStyle: { 
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#10b981' },
              { offset: 1, color: '#059669' }
            ])
          }
        }],
        grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
        animation: true,
        animationDuration: 1200
      });
    }

    // COD Rate Chart (COD vs CC Distribution)
    if (codRateChartRef.current && data.cod_rate_by_receiver_mode?.length > 0) {
      const chart = echarts.init(codRateChartRef.current);
      chart.setOption({
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c} ({d}%)'
        },
        legend: {
          orient: 'vertical',
          left: 'left',
          textStyle: { fontSize: 10 }
        },
        series: [{
          name: 'طريقة الدفع',
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          data: data.cod_rate_by_receiver_mode.map((item: any) => ({
            value: item.val,
            name: item.dt === 'COD' ? 'الدفع عند الاستلام' : 'الدفع بالبطاقة'
          })),
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            show: false,
            position: 'center'
          },
          emphasis: {
            label: {
              show: true,
              fontSize: '20',
              fontWeight: 'bold'
            }
          },
          labelLine: {
            show: false
          }
        }],
        color: ['#f59e0b', '#3b82f6'],
        animation: true,
        animationDuration: 1500
      });
    }

    // COD Rate by Destination Trends
    if (trendsChartRef.current && data.cod_rate_by_destination?.length > 0) {
      const chart = echarts.init(trendsChartRef.current);
      chart.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: function(params: any) {
            return `${params[0].name}<br/>معدل الدفع عند الاستلام: ${(params[0].value * 100).toFixed(1)}%`;
          }
        },
        xAxis: {
          type: 'category',
          data: data.cod_rate_by_destination.map((item: any) => item.dt),
          axisLabel: { rotate: 45, fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          axisLabel: { 
            fontSize: 10,
            formatter: function(value: number) {
              return (value * 100).toFixed(0) + '%';
            }
          }
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
              { offset: 1, color: 'transparent' }
            ])
          }
        }],
        grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
        animation: true,
        animationDuration: 1000
      });
    }

    // COD Rate Chart
    if (codRateChartRef.current && data.cod_rate_daily?.length > 0) {
      const chart = echarts.init(codRateChartRef.current);
      chart.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: (params: any) => {
            const value = (params[0].value * 100).toFixed(1);
            return `${params[0].name}<br/>معدل COD: ${value}%`;
          },
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          borderColor: '#333',
          textStyle: { color: '#fff' }
        },
        xAxis: {
          type: 'category',
          data: data.cod_rate_daily.map((item: any) => item.date || item.dt),
          axisLabel: { rotate: 45, fontSize: 10 }
        },
        yAxis: {
          type: 'value',
          axisLabel: { 
            formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
            fontSize: 10
          },
          min: 0,
          max: 1
        },
        series: [{
          name: 'معدل COD',
          type: 'bar',
          data: data.cod_rate_daily.map((item: any) => item.rate || item.val),
          itemStyle: { 
            color: (params: any) => {
              const value = params.value;
              if (value > 0.7) return '#ef4444'; // أحمر للقيم العالية
              if (value > 0.5) return '#f59e0b'; // برتقالي للقيم المتوسطة
              return '#10b981'; // أخضر للقيم المنخفضة
            }
          },
          label: {
            show: true,
            position: 'top',
            formatter: (params: any) => `${(params.value * 100).toFixed(1)}%`,
            fontSize: 9
          }
        }],
        grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
        animation: true,
        animationDuration: 800
      });
    }

    // Trends Overview Chart
    if (trendsChartRef.current && data.orders_daily?.length > 0) {
      const chart = echarts.init(trendsChartRef.current);
      const dates = data.orders_daily.map((item: any) => item.date || item.dt);
      const orders = data.orders_daily.map((item: any) => item.count || item.val);
      
      chart.setOption({
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          borderColor: '#333',
          textStyle: { color: '#fff' }
        },
        legend: {
          data: ['الطلبات اليومية', 'المتوسط المتحرك'],
          top: 10
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisLabel: { rotate: 45, fontSize: 10 }
        },
        yAxis: { 
          type: 'value',
          axisLabel: { fontSize: 10 }
        },
        series: [
          {
            name: 'الطلبات اليومية',
            type: 'bar',
            data: orders,
            itemStyle: { color: '#3b82f6', opacity: 0.7 }
          },
          {
            name: 'المتوسط المتحرك',
            type: 'line',
            data: calculateMovingAverage(orders, 3),
            smooth: true,
            lineStyle: { width: 2, color: '#ef4444' },
            symbol: 'circle',
            symbolSize: 4
          }
        ],
        grid: { left: '3%', right: '4%', bottom: '15%', top: '15%', containLabel: true },
        animation: true,
        animationDuration: 1500
      });
    }
  }, []);

  useEffect(() => {
    if (metrics && Object.keys(metrics).length > 0 && !isLoading) {
      setTimeout(() => {
        initializeCharts(metrics);
      }, 100);
    }
  }, [metrics, isLoading, initializeCharts]);

  const calculateMovingAverage = (data: number[], window: number) => {
    const result = [];
    for (let i = 0; i < data.length; i++) {
      if (i < window - 1) {
        result.push(null);
      } else {
        const sum = data.slice(i - window + 1, i + 1).reduce((a, b) => a + b, 0);
        result.push(sum / window);
      }
    }
    return result;
  };

  const calculateKPIs = () => {
    if (!metrics || !metrics.orders_daily) return null;

    const totalOrders = metrics.orders_daily.reduce((sum: number, item: any) => sum + (item.count || item.val || 0), 0);
    const avgDailyOrders = Math.round(totalOrders / metrics.orders_daily.length);
    
    const avgCodRate = metrics.cod_rate_daily?.length > 0 
      ? (metrics.cod_rate_daily.reduce((sum: number, item: any) => sum + (item.rate || item.val || 0), 0) / metrics.cod_rate_daily.length * 100)
      : 0;
    
    const topDestination = metrics.avg_cod_amount_destination?.length > 0 
      ? metrics.avg_cod_amount_destination.reduce((prev: any, current: any) => 
          (prev.avg_amount || prev.val || 0) > (current.avg_amount || current.val || 0) ? prev : current
        )
      : null;

    // Calculate trends
    const recentOrders = metrics.orders_daily.slice(-7);
    const previousOrders = metrics.orders_daily.slice(-14, -7);
    const recentAvg = recentOrders.length > 0 ? recentOrders.reduce((sum: number, item: any) => sum + (item.count || item.val || 0), 0) / recentOrders.length : 0;
    const previousAvg = previousOrders.length > 0 ? previousOrders.reduce((sum: number, item: any) => sum + (item.count || item.val || 0), 0) / previousOrders.length : 0;
    const trendPercentage = previousAvg > 0 ? ((recentAvg - previousAvg) / previousAvg * 100) : 0;

    return {
      totalOrders,
      avgDailyOrders,
      avgCodRate: avgCodRate.toFixed(1),
      topDestination: topDestination ? (topDestination.destination || topDestination.dim) : 'غير متوفر',
      topDestinationAmount: topDestination ? (topDestination.avg_amount || topDestination.val || 0).toFixed(2) : '0',
      trendPercentage: trendPercentage.toFixed(1),
      isPositiveTrend: trendPercentage > 0
    };
  };

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-6">
                <div className="h-4 bg-muted rounded w-3/4 mb-2"></div>
                <div className="h-8 bg-muted rounded w-1/2 mb-2"></div>
                <div className="h-3 bg-muted rounded w-2/3"></div>
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="text-center py-12">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">جاري تحليل البيانات...</p>
        </div>
      </div>
    );
  }

  if (!metrics || Object.keys(metrics).length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">لا توجد بيانات متاحة</h3>
          <p className="text-muted-foreground">يرجى التأكد من أن الخادم يعمل وأن هناك بيانات متاحة للعرض</p>
          <p className="text-sm text-muted-foreground mt-2">أو اختيار تشغيل صحيح من القائمة أعلاه</p>
        </div>
      </div>
    );
  }

  const kpis = calculateKPIs();

  return (
    <div className="p-6 space-y-6 h-full overflow-auto">
      {/* KPI Cards */}
      {kpis && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <Card className="hover:shadow-lg transition-all duration-300 border-primary/20 bg-gradient-to-br from-card to-primary/5">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">إجمالي الطلبات</CardTitle>
              <Package className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{kpis.totalOrders.toLocaleString()}</div>
              <div className="flex items-center text-xs text-muted-foreground">
                <Calendar className="h-3 w-3 mr-1" />
                للفترة المحددة
              </div>
            </CardContent>
          </Card>

          <Card className="hover:shadow-lg transition-all duration-300 border-secondary/20 bg-gradient-to-br from-card to-secondary/5">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">متوسط الطلبات اليومية</CardTitle>
              <TrendingUp className="h-4 w-4 text-secondary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{kpis.avgDailyOrders}</div>
              <div className="flex items-center text-xs">
                {kpis.isPositiveTrend ? (
                  <ArrowUpRight className="h-3 w-3 text-green-500 mr-1" />
                ) : (
                  <ArrowDownRight className="h-3 w-3 text-red-500 mr-1" />
                )}
                <span className={kpis.isPositiveTrend ? 'text-green-500' : 'text-red-500'}>
                  {Math.abs(parseFloat(kpis.trendPercentage))}%
                </span>
                <span className="text-muted-foreground mr-1">عن الأسبوع الماضي</span>
              </div>
            </CardContent>
          </Card>

          <Card className="hover:shadow-lg transition-all duration-300 border-orange-500/20 bg-gradient-to-br from-card to-orange-500/5">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">معدل الدفع عند التسليم</CardTitle>
              <DollarSign className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{kpis.avgCodRate}%</div>
              <div className="flex items-center text-xs text-muted-foreground">
                <Activity className="h-3 w-3 mr-1" />
                من إجمالي الطلبات
              </div>
            </CardContent>
          </Card>

          <Card className="hover:shadow-lg transition-all duration-300 border-purple-500/20 bg-gradient-to-br from-card to-purple-500/5">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">أعلى وجهة</CardTitle>
              <MapPin className="h-4 w-4 text-purple-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold truncate">{kpis.topDestination}</div>
              <div className="flex items-center text-xs text-muted-foreground">
                <DollarSign className="h-3 w-3 mr-1" />
                {kpis.topDestinationAmount} ر.س
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Charts */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">نظرة عامة</TabsTrigger>
          <TabsTrigger value="trends">الاتجاهات</TabsTrigger>
          <TabsTrigger value="performance">الأداء</TabsTrigger>
          <TabsTrigger value="geography">الجغرافيا</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <LineChart className="h-5 w-5 text-primary" />
                    اتجاه الطلبات اليومية
                  </CardTitle>
                  <Badge variant="secondary">Live</Badge>
                </div>
                <CardDescription>تتبع كمية الطلبات عبر الزمن</CardDescription>
              </CardHeader>
              <CardContent>
                <div ref={ordersChartRef} className="h-[300px] w-full"></div>
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-orange-500" />
                    معدل الدفع عند التسليم
                  </CardTitle>
                  <Badge variant="outline">يومي</Badge>
                </div>
                <CardDescription>نسبة الطلبات المدفوعة عند التسليم</CardDescription>
              </CardHeader>
              <CardContent>
                <div ref={codRateChartRef} className="h-[300px] w-full"></div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="trends" className="space-y-6">
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-secondary" />
                تحليل الاتجاهات المتقدم
              </CardTitle>
              <CardDescription>الطلبات اليومية مع المتوسط المتحرك</CardDescription>
            </CardHeader>
            <CardContent>
              <div ref={trendsChartRef} className="h-[400px] w-full"></div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="performance" className="space-y-6">
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-green-500" />
                مؤشرات الأداء الرئيسية
              </CardTitle>
              <CardDescription>تحليل شامل للأداء والكفاءة</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-12 text-muted-foreground">
                <BarChart3 className="h-12 w-12 mx-auto mb-4" />
                <p>سيتم إضافة مؤشرات أداء إضافية قريباً</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="geography" className="space-y-6">
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-purple-500" />
                التوزيع الجغرافي
              </CardTitle>
              <CardDescription>متوسط مبلغ الدفع عند التسليم حسب الوجهة</CardDescription>
            </CardHeader>
            <CardContent>
              <div ref={codAmountChartRef} className="h-[500px] w-full"></div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}