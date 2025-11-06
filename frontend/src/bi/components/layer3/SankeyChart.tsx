"use client";

import React, { useMemo } from "react";
import type { Layer3Intelligence } from "../../data/intelligence";
import { EChartBase } from "../layer2/EChartBase";

type SankeyChartProps = {
  data: Layer3Intelligence["sankey"];
  height?: number;
};

export const SankeyChart: React.FC<SankeyChartProps> = ({ data, height = 360 }) => {
  const option = useMemo(() => {
    const nodes = data.nodes.map((name) => ({ name }));
    const links = data.links.map((link) => ({
      source: link.source,
      target: link.target,
      value: Number.isFinite(link.value) ? link.value : 0,
      label: link.label,
    }));
    return {
      tooltip: {
        trigger: "item",
        formatter: (params: any) => {
          if (params.dataType === "edge") {
            const unit = data.unit ? ` ${data.unit}` : "";
            return `${params.data.source} → ${params.data.target}<br/>${params.data.value.toFixed(2)}${unit}`;
          }
          return params.name;
        },
      },
      series: [
        {
          type: "sankey",
          nodeAlign: "justify",
          data: nodes,
          links,
          emphasis: {
            focus: "adjacency",
          },
          label: {
            color: "inherit",
          },
          lineStyle: {
            color: "source",
            curveness: 0.4,
          },
        },
      ],
    };
  }, [data]);

  return <EChartBase option={option} height={height} />;
};

export default SankeyChart;
