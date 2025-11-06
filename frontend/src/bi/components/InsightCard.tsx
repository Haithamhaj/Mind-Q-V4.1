'use client';

import * as React from 'react';
import clsx from 'clsx';

import { normalizeLabelText } from '../utils/normalize';

type Driver = {
  dimension: string;
  value: string;
  impact?: number | null;
};

type InsightCardProps = {
  title: string;
  summary: string;
  severity?: 'low' | 'medium' | 'high';
  drivers?: Driver[];
  recommendations?: string[];
  nextSteps?: string[];
  metricsContext?: Record<string, unknown>;
  tags?: string[];
  onOpen?: () => void;
  source?: string;
};

const severityConfig: Record<string, { label: string; className: string }> = {
  high: { label: 'خطورة مرتفعة', className: 'bg-rose-500/10 text-rose-500 dark:text-rose-300' },
  medium: { label: 'متوسط', className: 'bg-amber-500/10 text-amber-500 dark:text-amber-300' },
  low: { label: 'منخفض', className: 'bg-emerald-500/10 text-emerald-500 dark:text-emerald-300' },
  default: { label: 'غير مصنف', className: 'bg-muted text-muted-foreground' },
};

export const InsightCard: React.FC<InsightCardProps> = ({
  title,
  summary,
  severity = 'medium',
  drivers = [],
  recommendations,
  nextSteps,
  metricsContext,
  tags,
  onOpen,
  source,
}) => {
  const badge = severityConfig[severity] ?? severityConfig.default;
  const movement = typeof metricsContext?.movement === 'string' ? metricsContext.movement : undefined;
  const deltaText = typeof metricsContext?.delta_text === 'string' ? metricsContext.delta_text : undefined;
  const recommendationsList = (recommendations ?? []).filter(Boolean);
  const nextStepsList = (nextSteps ?? []).filter(Boolean);
  const displayTags = (tags ?? []).map((tag) => normalizeLabelText(tag)).filter(Boolean).slice(0, 3);
  const primaryNextStep = nextStepsList[0];

  return (
    <article
      dir='rtl'
      className='flex flex-col gap-3 rounded-2xl border border-border/60 bg-background/70 p-4 shadow-sm transition-all duration-200 ease-out hover:-translate-y-1 hover:shadow-lg'
    >
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div className='flex flex-col gap-2'>
          <h3 className='text-base font-semibold'>{title}</h3>
          {displayTags.length > 0 && (
            <div className='flex flex-wrap gap-2 text-[10px]'>
              {displayTags.map((tag) => (
                <span key={tag} className='rounded-full border border-primary/30 px-2 py-0.5 text-primary/80'>
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
        <span className={clsx('rounded-full px-3 py-1 text-xs font-medium', badge.className)}>{badge.label}</span>
      </div>

      {(movement || deltaText) && (
        <div className='flex flex-wrap items-center gap-2 text-xs text-primary/80'>
          {movement && <span className='font-medium'>{movement}</span>}
          {deltaText && <span className='rounded-full bg-primary/10 px-2 py-0.5'>{deltaText}</span>}
        </div>
      )}

      <p className='text-sm text-muted-foreground'>{summary}</p>

      {drivers.length > 0 && (
        <div className='rounded-xl border border-dashed border-border/50 bg-muted/40 p-3'>
          <span className='mb-2 block text-xs font-medium text-muted-foreground'>أبرز المحركات</span>
          <ul className='flex flex-col gap-2 text-sm'>
            {drivers.map((driver, index) => {
              const dimensionLabel = normalizeLabelText(driver.dimension);
              const driverValue = normalizeLabelText(driver.value);
              return (
                <li key={`${driver.dimension}-${index}`} className='flex items-center justify-between gap-3'>
                  <span className='truncate font-medium'>{dimensionLabel || driver.dimension}</span>
                  <span className='truncate text-sm text-muted-foreground'>{driverValue || driver.value}</span>
                {typeof driver.impact === 'number' && !Number.isNaN(driver.impact) && (
                  <span className='text-xs font-medium text-primary/80'>{(driver.impact * 100).toFixed(1)}%</span>
                )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {recommendationsList.length > 0 && (
        <div className='rounded-xl border border-primary/20 bg-primary/5 p-3'>
          <span className='mb-2 block text-xs font-medium text-primary/80'>توصيات فورية</span>
          <ul className='flex list-disc flex-col gap-1 pe-4 text-sm text-primary/90'>
            {recommendationsList.slice(0, 3).map((item, index) => (
              <li key={`rec-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      <div className='flex flex-col gap-2 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between'>
        <div className='flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3'>
          {source && <span>المصدر: {source}</span>}
          {primaryNextStep && <span className='text-primary/80'>الخطوة التالية: {primaryNextStep}</span>}
        </div>
        <button
          type='button'
          onClick={onOpen}
          className='self-start rounded-full px-3 py-1 font-medium text-primary transition hover:bg-primary/10 sm:self-auto'
        >
          فتح التحليل
        </button>
      </div>
    </article>
  );
};

export default InsightCard;

