"use client";

import React, { useMemo } from "react";
import type { Layer3Intelligence } from "../../data/intelligence";
import { EChartBase } from "../layer2/EChartBase";

type NetworkGraphProps = {
  data: Layer3Intelligence["network"];
  height?: number;
};

export const NetworkGraph: React.FC<NetworkGraphProps> = ({ data, height = 380 }) => {
  const option = useMemo(() => {
    const categories = data.categories ?? Array.from(new Set(data.nodes.map((node) => node.type)));
    const formattedNodes = data.nodes.map((node) => ({
      name: node.id,
      value: node.score ?? 0,
      category: categories.indexOf(node.type),
      symbolSize: Math.max(24, Math.min(64, (node.score ?? 0.2) * 80)),
      label: {
        show: true,
        formatter: node.label,
      },
    }));
    const formattedEdges = data.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      value: edge.value,
      label: {
        show: !!edge.label,
        formatter: edge.label,
      },
    }));
    return {
      tooltip: {
        trigger: "item",
        formatter: (params: any) => {
          if (params.dataType === "node") {
            return `${params.name}<br/>Score: ${(params.value ?? 0).toFixed(2)}`;
          }
          if (params.dataType === "edge") {
            return `${params.data.source} → ${params.data.target}<br/>Strength: ${params.data.value.toFixed(2)}`;
          }
          return "";
        },
      },
      legend: {
        data: categories,
        left: "left",
      },
      series: [
        {
          type: "graph",
          layout: "force",
          roam: true,
          draggable: true,
          label: {
            position: "right",
            formatter: "{b}",
          },
          force: {
            repulsion: 240,
            gravity: 0.08,
            edgeLength: 180,
          },
          categories: categories.map((name) => ({ name })),
          data: formattedNodes,
          links: formattedEdges,
          lineStyle: {
            width: 2,
            color: "source",
            curveness: 0.2,
          },
        },
      ],
    };
  }, [data]);

  return <EChartBase option={option} height={height} />;
};

export default NetworkGraph;
