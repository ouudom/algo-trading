'use client';

import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import type { EquityDataPoint } from '@/types';
import { formatCurrency } from '@/lib/utils';

interface EquityCurveProps {
  data: EquityDataPoint[];
  /** Height of the chart in pixels */
  height?: number;
  /** Starting equity value used to draw the reference line */
  initialEquity?: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: '2-digit',
    });
  } catch {
    return iso;
  }
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const value = payload[0].value;
  return (
    <div
      className="bg-gray-800 border border-gray-700 rounded-md px-3 py-2 shadow-lg"
      role="tooltip"
    >
      <p className="text-xs text-gray-400 mb-0.5">{fmtDate(label ?? '')}</p>
      <p className="text-sm font-semibold text-gray-100 tabular-nums">
        {formatCurrency(value)}
      </p>
    </div>
  );
}

function formatYAxis(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value}`;
}

export default function EquityCurve({
  data,
  height = 280,
  initialEquity,
}: EquityCurveProps) {
  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center bg-gray-900 rounded-lg border border-gray-800"
        style={{ height }}
        aria-label="Equity curve chart — no data"
      >
        <p className="text-sm text-gray-600">No equity data available</p>
      </div>
    );
  }

  const refLine = initialEquity ?? data[0]?.equity;

  // Compute a tight Y-axis domain so the curve fills the chart vertically
  const values = data.map((d) => d.equity);
  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);
  const range = dataMax - dataMin || dataMax * 0.02; // fallback for flat lines
  const pad = range * 0.15;
  const yMin = dataMin - pad;
  const yMax = dataMax + pad;

  return (
    <div aria-label="Equity curve chart" role="img">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={data}
          margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#1f2937"
            vertical={false}
          />
          <XAxis
            dataKey="date"
            tickFormatter={fmtDate}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            minTickGap={60}
          />
          <YAxis
            tickFormatter={formatYAxis}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={64}
            domain={[yMin, yMax]}
          />
          <Tooltip content={<CustomTooltip />} />
          {refLine !== undefined && (
            <ReferenceLine
              y={refLine}
              stroke="#374151"
              strokeDasharray="4 4"
              strokeWidth={1}
            />
          )}
          <Line
            type="monotone"
            dataKey="equity"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: '#3b82f6', stroke: '#1e3a5f', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
