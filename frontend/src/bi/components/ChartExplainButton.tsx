'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Loader2, Sparkles } from 'lucide-react';
import { useLanguage } from '@/context/language-context';
import { Card, CardContent } from '@/components/ui/card';

export interface ChartExplainButtonProps {
  /** Chart title or identifier */
  chartTitle: string;
  /** Chart type for context */
  chartType?: 'line' | 'bar' | 'area' | 'funnel' | 'treemap' | 'combo' | 'pie';
  /** Chart data summary for LLM context */
  dataSummary?: string;
  /** Callback to request LLM explanation */
  onExplain?: (context: {
    title: string;
    type?: string;
    summary?: string;
  }) => Promise<string>;
  /** Current explanation text */
  explanation?: string;
  /** Loading state */
  isLoading?: boolean;
  /** Compact button style */
  compact?: boolean;
}

/**
 * A button component that requests LLM explanation for any chart/visualization.
 * Can be used with Layer1Chart, raw metrics charts, trends, or any custom visualization.
 */
export const ChartExplainButton: React.FC<ChartExplainButtonProps> = ({
  chartTitle,
  chartType,
  dataSummary,
  onExplain,
  explanation,
  isLoading = false,
  compact = false,
}) => {
  const { translate } = useLanguage();
  const [localExplanation, setLocalExplanation] = useState<string | null>(null);
  const [localLoading, setLocalLoading] = useState(false);

  const currentExplanation = explanation ?? localExplanation;
  const currentLoading = isLoading || localLoading;

  const handleExplainClick = async () => {
    if (!onExplain || currentLoading) return;

    setLocalLoading(true);
    try {
      const result = await onExplain({
        title: chartTitle,
        type: chartType,
        summary: dataSummary,
      });
      setLocalExplanation(result);
    } catch (error) {
      console.error('[ChartExplainButton] Failed to get explanation:', error);
      setLocalExplanation(translate('فشل في الحصول على الشرح'));
    } finally {
      setLocalLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      <Button
        onClick={handleExplainClick}
        disabled={currentLoading || !onExplain}
        variant="outline"
        size={compact ? 'sm' : 'default'}
        className="gap-2"
      >
        {currentLoading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            {translate('جاري التحليل...')}
          </>
        ) : (
          <>
            <Sparkles className="h-4 w-4" />
            {translate('اشرح بواسطة LLM')}
          </>
        )}
      </Button>

      {currentExplanation && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="pt-4">
            <div className="flex items-start gap-2">
              <Sparkles className="mt-1 h-4 w-4 text-primary flex-shrink-0" />
              <p className="text-sm text-foreground whitespace-pre-wrap">
                {currentExplanation}
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default ChartExplainButton;
