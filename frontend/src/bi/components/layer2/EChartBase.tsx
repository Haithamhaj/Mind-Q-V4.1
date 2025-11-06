"use client";

import React, { useEffect, useRef } from "react";
import clsx from "clsx";
import { use, init, getInstanceByDom } from "echarts/core";
import type { EChartsCoreOption, EChartsType } from "echarts/core";
import { BarChart, LineChart, PieChart, ScatterChart, HeatmapChart, BoxplotChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  ToolboxComponent,
  DataZoomComponent,
  VisualMapComponent,
  BrushComponent,
  DatasetComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  HeatmapChart,
  BoxplotChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  ToolboxComponent,
  DataZoomComponent,
  VisualMapComponent,
  BrushComponent,
  DatasetComponent,
  MarkLineComponent,
  MarkAreaComponent,
  CanvasRenderer,
]);

type EChartBaseProps = {
  option: EChartsCoreOption;
  height?: number;
  className?: string;
  onReady?: (instance: EChartsType) => void;
};

export const EChartBase: React.FC<EChartBaseProps> = ({ option, height = 320, className, onReady }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const target = containerRef.current;
    if (!target) {
      return;
    }

    let throttleTimer: ReturnType<typeof setTimeout> | null = null;
    const throttle = (fn: () => void, delay = 80) => {
      if (throttleTimer) return;
      throttleTimer = setTimeout(() => {
        throttleTimer = null;
        fn();
      }, delay);
    };

    let instance = getInstanceByDom(target as HTMLDivElement);
    if (!instance) {
      instance = init(target, undefined, { renderer: "canvas" });
    }

    instance.setOption(option, { notMerge: false, lazyUpdate: true });

    onReady?.(instance);

    const resize = () => {
      if (!instance?.isDisposed()) {
        instance.resize();
      }
    };

    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => throttle(resize)) : null;
    observer?.observe(target);
    const onWindowResize = () => throttle(resize);
    window.addEventListener("resize", onWindowResize);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", onWindowResize);
      if (instance && !instance.isDisposed()) {
        instance.dispose();
      }
    };
  }, [option, onReady]);

  return <div ref={containerRef} className={clsx("w-full", className)} style={{ height }} />;
};

export default EChartBase;
