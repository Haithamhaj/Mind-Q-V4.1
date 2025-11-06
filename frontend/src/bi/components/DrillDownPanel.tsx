"use client";

import React, { useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ChevronDown,
  ChevronRight,
  TrendingDown,
  TrendingUp,
  ZoomIn,
} from "lucide-react";

export type DrillDownLevel = {
  dimension: string;
  dimensionLabel: string;
  value: string;
};

export type DrillDownData = {
  value: string;
  label: string;
  count: number;
  percentage: number;
  metric?: number;
  trend?: "up" | "down" | "neutral";
  children?: DrillDownData[];
};

export type DrillDownPanelProps = {
  title: string;
  data: DrillDownData[];
  onDrillDown?: (path: DrillDownLevel[]) => void;
  maxLevels?: number;
};

const DrillDownItem: React.FC<{
  item: DrillDownData;
  level: number;
  path: DrillDownLevel[];
  onExpand: (item: DrillDownData, path: DrillDownLevel[]) => void;
}> = ({ item, level, path, onExpand }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const hasChildren = item.children && item.children.length > 0;

  const handleToggle = () => {
    if (hasChildren) {
      setIsExpanded(!isExpanded);
      if (!isExpanded) {
        onExpand(item, path);
      }
    }
  };

  return (
    <div className="my-1">
      <div
        className={`flex items-center gap-2 rounded-md p-2 transition-colors ${
          hasChildren ? "cursor-pointer hover:bg-muted" : ""
        }`}
        style={{ paddingRight: `${level * 1.5 + 0.5}rem` }}
        onClick={handleToggle}
      >
        {hasChildren ? (
          isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )
        ) : (
          <div className="h-4 w-4" />
        )}
        
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{item.label}</span>
            <Badge variant="outline" className="text-xs">
              {item.count.toLocaleString("ar-SA")}
            </Badge>
            <span className="text-sm text-muted-foreground">
              ({item.percentage.toFixed(1)}%)
            </span>
          </div>
        </div>

        {item.metric !== undefined && (
          <div className="flex items-center gap-1">
            <span className="text-sm font-medium">
              {item.metric.toLocaleString("ar-SA", {
                minimumFractionDigits: 0,
                maximumFractionDigits: 2,
              })}
            </span>
            {item.trend === "up" && (
              <TrendingUp className="h-4 w-4 text-green-500" />
            )}
            {item.trend === "down" && (
              <TrendingDown className="h-4 w-4 text-red-500" />
            )}
          </div>
        )}
      </div>

      {isExpanded && hasChildren && (
        <div className="mt-1">
          {item.children!.map((child, idx) => (
            <DrillDownItem
              key={idx}
              item={child}
              level={level + 1}
              path={[...path, { dimension: "", dimensionLabel: "", value: item.value }]}
              onExpand={onExpand}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const DrillDownPanel: React.FC<DrillDownPanelProps> = ({
  title,
  data,
  onDrillDown,
  maxLevels = 3,
}) => {
  const handleExpand = (item: DrillDownData, path: DrillDownLevel[]) => {
    if (onDrillDown) {
      onDrillDown([...path, { dimension: "", dimensionLabel: "", value: item.value }]);
    }
  };

  const totalCount = useMemo(() => {
    return data.reduce((sum, item) => sum + item.count, 0);
  }, [data]);

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ZoomIn className="h-5 w-5" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">لا توجد بيانات للتحليل التفصيلي</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ZoomIn className="h-5 w-5" />
          {title}
        </CardTitle>
        <CardDescription>
          إجمالي: {totalCount.toLocaleString("ar-SA")} سجل
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {data.map((item, idx) => (
            <DrillDownItem
              key={idx}
              item={item}
              level={0}
              path={[]}
              onExpand={handleExpand}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
};
