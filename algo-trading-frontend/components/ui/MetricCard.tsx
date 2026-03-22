import React from 'react';
import { cn } from '@/lib/utils';

interface MetricCardProps {
  label: string;
  value: string | number;
  delta?: string | number;
  deltaPositive?: boolean;
  /** Optional sublabel shown below the value */
  sublabel?: string;
  className?: string;
  /** Optional accent color on the left border */
  accent?: 'blue' | 'green' | 'red' | 'yellow' | 'none';
}

const ACCENT_CLASSES: Record<NonNullable<MetricCardProps['accent']>, string> = {
  blue: 'border-l-blue-500',
  green: 'border-l-green-500',
  red: 'border-l-red-500',
  yellow: 'border-l-yellow-500',
  none: 'border-l-transparent',
};

export default function MetricCard({
  label,
  value,
  delta,
  deltaPositive,
  sublabel,
  className,
  accent = 'none',
}: MetricCardProps) {
  const hasDelta = delta !== undefined && delta !== null;
  const isPositive = deltaPositive ?? (typeof delta === 'number' ? delta >= 0 : true);

  return (
    <article
      className={cn(
        'bg-gray-900 border border-gray-800 rounded-lg p-4',
        'border-l-4',
        ACCENT_CLASSES[accent],
        className
      )}
      aria-label={`${label}: ${value}`}
    >
      {/* Label */}
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
        {label}
      </p>

      {/* Value */}
      <p className="text-2xl font-bold text-gray-100 leading-none tabular-nums">
        {value}
      </p>

      {/* Delta + sublabel row */}
      {(hasDelta || sublabel) && (
        <div className="flex items-center gap-2 mt-2">
          {hasDelta && (
            <span
              className={cn(
                'inline-flex items-center text-xs font-medium',
                isPositive ? 'text-green-400' : 'text-red-400'
              )}
              aria-label={`Change: ${delta}`}
            >
              <span aria-hidden="true">{isPositive ? '▲' : '▼'}</span>
              &nbsp;{delta}
            </span>
          )}
          {sublabel && (
            <span className="text-xs text-gray-500">{sublabel}</span>
          )}
        </div>
      )}
    </article>
  );
}
