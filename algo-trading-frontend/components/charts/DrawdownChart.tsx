'use client';

import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import type { DrawdownDataPoint } from '@/types';
import { formatPct } from '@/lib/utils';

interface DrawdownChartProps {
  data: DrawdownDataPoint[];
  /** Height of the chart in pixels */
  height?: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const value = payload[0].value;
  return (
    <div
      className="bg-gray-800 border border-gray-700 rounded-md px-3 py-2 shadow-lg"
      role="tooltip"
    >
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className="text-sm font-semibold text-red-400 tabular-nums">
        {formatPct(value)}
      </p>
    </div>
  );
}

function formatYAxisPct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

export default function DrawdownChart({ data, height = 200 }: DrawdownChartProps) {
  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center bg-gray-900 rounded-lg border border-gray-800"
        style={{ height }}
        aria-label="Drawdown chart — no data"
      >
        <p className="text-sm text-gray-600">No drawdown data available</p>
      </div>
    );
  }

  return (
    <div aria-label="Drawdown chart" role="img">
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart
          data={data}
          margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
        >
          <defs>
            <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#1f2937"
            vertical={false}
          />
          <XAxis
            dataKey="date"
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            minTickGap={40}
          />
          <YAxis
            tickFormatter={formatYAxisPct}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={48}
            /* drawdown values are negative; invert domain for intuitive display */
            domain={['dataMin', 0]}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke="#374151" strokeWidth={1} />
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="#ef4444"
            strokeWidth={1.5}
            fill="url(#drawdownGradient)"
            activeDot={{ r: 4, fill: '#ef4444', stroke: '#7f1d1d', strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
