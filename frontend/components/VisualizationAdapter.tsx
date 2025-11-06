"use client"

import type { FC } from "react"
import dynamic from "next/dynamic"
import { BiChart } from "@/components/bi-chart"

const HeatmapChart = dynamic(() => import("@/src/bi/components/layer2/HeatmapChart").then(m => m.HeatmapChart), { ssr: false })
const BoxPlotChart = dynamic(() => import("@/src/bi/components/layer2/BoxPlotChart").then(m => m.BoxPlotChart), { ssr: false })
const WaterfallChart = dynamic(() => import("@/src/bi/components/layer2/WaterfallChart").then(m => m.WaterfallChart), { ssr: false })
const ScatterChart = dynamic(() => import("@/src/bi/components/layer2/ScatterChart").then(m => m.ScatterChart), { ssr: false })
const MultiAxisLineChart = dynamic(() => import("@/src/bi/components/layer2/MultiAxisLineChart").then(m => m.MultiAxisLineChart), { ssr: false })

export type VizSpec = {
  engine?: "echarts"
  chartType?: string
  xKey?: string
  valueKey?: string
}

export const VisualizationAdapter: FC<{
  data: Array<Record<string, unknown>>
  viz: VizSpec
  height?: number
}> = ({ data, viz, height = 320 }) => {
  const type = (viz.chartType || "bar").toLowerCase()

  switch (type) {
    case "heatmap":
      return <HeatmapChart data={data} height={height} />
    case "boxplot":
      return <BoxPlotChart data={data} height={height} />
    case "waterfall":
      return <WaterfallChart data={data} height={height} />
    case "scatter":
      return <ScatterChart data={data} height={height} />
    case "multi-axis":
    case "multi-line":
      return <MultiAxisLineChart data={data} height={height} />
    default:
      return (
        <BiChart
          data={data}
          chartType={type}
          xKey={viz.xKey ?? "dt"}
          valueKey={viz.valueKey ?? "val"}
          height={height}
        />
      )
  }
}

export default VisualizationAdapter


