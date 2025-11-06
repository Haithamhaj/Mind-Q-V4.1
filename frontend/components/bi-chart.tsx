import type { FC } from "react"
import { useMemo } from "react"
import type { EChartsCoreOption } from "echarts"
import { EChartBase } from "@/src/bi/components/layer2/EChartBase"

const DEFAULT_COLORS = ["#2563eb", "#10b981", "#f97316", "#8b5cf6", "#ec4899", "#14b8a6", "#fbbf24", "#0ea5e9"]

interface BiChartProps {
  data: Array<Record<string, unknown>>
  chartType: "line" | "area" | "bar" | "pie" | string
  xKey: string
  valueKey?: string
  height?: number
}

export const BiChart: FC<BiChartProps> = ({ data, chartType, xKey, valueKey = "val", height = 320 }) => {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-sm text-muted-foreground">
        No data available for this query.
      </div>
    )
  }

  const option = useMemo<EChartsCoreOption>(() => {
    const first = data[0] ?? {}
    const resolvedXKey = xKey in first ? xKey : Object.keys(first)[0]
    const resolvedValueKey =
      valueKey in first
        ? valueKey
        : (Object.keys(first).find((k) => typeof (first as any)[k] === "number") ?? valueKey)
    const locale = typeof document !== "undefined" ? document.documentElement.lang || "ar" : "ar"
    const nf = typeof Intl !== "undefined" ? new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }) : { format: (n: number) => String(n) }

    const base: EChartsCoreOption = {
      color: DEFAULT_COLORS,
      animation: true,
      animationDuration: 300,
      dataset: [{ source: data }],
      tooltip: {
        trigger: chartType === "pie" ? "item" : "axis",
        confine: true,
        axisPointer: chartType === "pie" ? undefined : { type: "cross" },
        formatter: (params: any) => {
          try {
            if (Array.isArray(params)) {
              const x = params[0]?.axisValueLabel ?? params[0]?.name ?? ""
              const lines = params.map((p) => {
                const seriesName = p.seriesName || valueKey
                let val = p.value
                if (p.encode && p.encode.y && Array.isArray(p.encode.y) && p.encode.y.length > 0) {
                  val = p.value?.[p.encode.y[0]]
                }
                const num = Number(val ?? 0)
                return `${p.marker || ""}${seriesName}: ${nf.format(num)}`
              })
              return `<div style="text-align:right">${x}<br/>${lines.join("<br/>")}</div>`
            }
            const name = params.name ?? ""
            let val = params.value
            if (params.encode && params.encode.value && Array.isArray(params.encode.value) && params.encode.value.length > 0) {
              val = params.value?.[params.encode.value[0]]
            }
            const num = Number(val ?? 0)
            return `<div style=\"text-align:right\">${name}<br/>${nf.format(num)}</div>`
          } catch {
            return undefined as any
          }
        },
      },
      toolbox: { feature: { saveAsImage: {}, dataZoom: {}, restore: {} } },
      dataZoom: chartType === "pie" ? undefined : [{ type: "inside" }, { type: "slider" }],
      brush: chartType === "pie" ? undefined : { toolbox: ["rect", "polygon", "keep", "clear"], xAxisIndex: "all" },
      grid: { top: 32, right: 24, bottom: 56, left: 56, containLabel: true },
      xAxis: chartType === "pie" ? undefined : { type: resolvedXKey === "dt" ? "category" : "category" },
      yAxis: chartType === "pie" ? undefined : { type: "value", splitLine: { show: true } },
      legend: chartType === "pie" ? { top: 0 } : undefined,
    }

    if (chartType === "pie") {
      return {
        ...base,
        series: [
          {
            type: "pie",
            radius: ["40%", "70%"],
            avoidLabelOverlap: true,
            encode: { itemName: resolvedXKey, value: resolvedValueKey },
          } as any,
        ],
      }
    }

    const seriesType = chartType === "area" ? "line" : chartType === "pareto" ? "bar" : chartType
    return {
      ...base,
      series: [
        {
          type: seriesType as any,
          smooth: seriesType === "line",
          areaStyle: chartType === "area" ? {} : undefined,
          encode: { x: resolvedXKey, y: resolvedValueKey },
          sampling: "lttb",
          progressive: 8000,
          large: seriesType === "bar",
          largeThreshold: 2000,
        } as any,
      ],
    }
  }, [data, chartType, xKey, valueKey])

  return <EChartBase option={option} height={height} />
}

export default BiChart
