"use client";

import * as echarts from "echarts";

import { mindQTokens } from "../../theme/tokens";

export type Layer1ThemeMode = "light" | "dark";

export const layer1Palette: string[] = [
  "#2563EB",
  "#9333EA",
  "#0EA5E9",
  "#16A34A",
  "#F97316",
  "#F43F5E",
  "#22C55E",
  "#F59E0B",
];

const baseFontFamily = mindQTokens.typography.family;

const createTheme = (mode: Layer1ThemeMode) => {
  const isDark = mode === "dark";
  const textColor = isDark ? "#E2E8F0" : "#0F172A";
  const subtleText = isDark ? "rgba(226, 232, 240, 0.7)" : "rgba(15, 23, 42, 0.65)";
  const gridColor = isDark ? "rgba(148, 163, 184, 0.18)" : "rgba(148, 163, 184, 0.24)";
  const axisLineColor = isDark ? "rgba(226, 232, 240, 0.45)" : "rgba(51, 65, 85, 0.35)";

  return {
    color: layer1Palette,
    backgroundColor: "transparent",
    textStyle: {
      color: textColor,
      fontFamily: baseFontFamily,
    },
    title: {
      textStyle: {
        color: textColor,
        fontWeight: 600,
      },
    },
    legend: {
      textStyle: {
        color: subtleText,
        fontSize: 12,
      },
    },
    tooltip: {
      backgroundColor: "rgba(15, 23, 42, 0.92)",
      borderColor: "rgba(148, 163, 184, 0.35)",
      borderWidth: 1,
      padding: 12,
      textStyle: {
        color: "#F8FAFC",
        fontSize: 12,
      },
    },
    axisPointer: {
      lineStyle: {
        color: "#38BDF8",
        width: 1.2,
      },
      crossStyle: {
        color: "#38BDF8",
      },
    },
    categoryAxis: {
      axisLabel: {
        color: subtleText,
        fontSize: 11,
      },
      axisLine: {
        lineStyle: {
          color: axisLineColor,
        },
      },
      splitLine: {
        show: false,
      },
    },
    valueAxis: {
      axisLabel: {
        color: subtleText,
        fontSize: 11,
      },
      axisLine: {
        lineStyle: {
          color: axisLineColor,
        },
      },
      splitLine: {
        lineStyle: {
          color: gridColor,
        },
      },
    },
    visualMap: {
      textStyle: {
        color: subtleText,
      },
    },
  };
};

const layer1Themes: Record<Layer1ThemeMode, echarts.EChartsCoreOption> = {
  light: createTheme("light"),
  dark: createTheme("dark"),
};

const registeredThemes = new Set<string>();

export const ensureLayer1Theme = (mode: Layer1ThemeMode): string => {
  const themeName = `layer1-${mode}`;
  if (!registeredThemes.has(themeName)) {
    echarts.registerTheme(themeName, layer1Themes[mode]);
    registeredThemes.add(themeName);
  }
  return themeName;
};
