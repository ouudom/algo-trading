'use client';

import React from 'react';
import {
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Scatter,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { getBacktestTrades } from '@/lib/api';
import type { BacktestTrade } from '@/types';

// ─── Props ────────────────────────────────────────────────────────────────────

interface TradeMapChartProps {
  runId: string;
  height?: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toMs(iso: string) {
  return new Date(iso).getTime();
}

function fmtDate(ms: number) {
  return new Date(ms).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: '2-digit',
  });
}

function fmtPrice(v: number) {
  return v.toFixed(4);
}

// ─── Custom entry marker (triangle ▲ / ▼) ────────────────────────────────────

interface MarkerPayload {
  cx?: number;
  cy?: number;
  payload?: {
    direction: number;
    reason?: string;
    pnl?: number;
    label: string;
    price: number;
    time: number;
  };
}

function EntryDot(props: MarkerPayload) {
  const { cx = 0, cy = 0, payload } = props;
  const isLong = payload?.direction === 1;
  const size = 7;
  // Triangle pointing up (long) or down (short)
  const path = isLong
    ? `M ${cx} ${cy - size} L ${cx + size} ${cy + size} L ${cx - size} ${cy + size} Z`
    : `M ${cx} ${cy + size} L ${cx + size} ${cy - size} L ${cx - size} ${cy - size} Z`;
  return <path d={path} fill={isLong ? '#22c55e' : '#ef4444'} stroke="none" opacity={0.9} />;
}

function ExitDot(props: MarkerPayload) {
  const { cx = 0, cy = 0, payload } = props;
  const reason = payload?.reason ?? '';
  const fill =
    reason === 'TP' ? '#22c55e'
    : reason === 'SL' ? '#ef4444'
    : '#6b7280';
  return <circle cx={cx} cy={cy} r={5} fill={fill} stroke="#111827" strokeWidth={1.5} opacity={0.95} />;
}

// ─── Custom tooltip ───────────────────────────────────────────────────────────

interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: MarkerPayload['payload'] }>;
}

function TradeTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  if (!d) return null;
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-md px-3 py-2 shadow-lg text-xs">
      <p className="text-gray-400 mb-1">{fmtDate(d.time)}</p>
      <p className="text-gray-200 font-semibold">{d.label}</p>
      <p className="text-gray-300 tabular-nums">{fmtPrice(d.price)}</p>
      {d.pnl !== undefined && (
        <p className={d.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
          {d.pnl >= 0 ? '+' : ''}{d.pnl.toFixed(2)}
        </p>
      )}
    </div>
  );
}

// ─── Main chart ───────────────────────────────────────────────────────────────

function Chart({ trades, height }: { trades: BacktestTrade[]; height: number }) {
  if (!trades.length) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ height }}
        aria-label="Trade map — no data"
      >
        <p className="text-sm text-gray-600">No trades to display</p>
      </div>
    );
  }

  // Build scatter points for entries and exits
  const entryPoints = trades.map((t) => ({
    time:      toMs(t.entry_time),
    price:     t.entry_price,
    direction: t.direction,
    label:     t.direction === 1 ? 'Long entry' : 'Short entry',
  }));

  const exitPoints = trades.map((t) => ({
    time:   toMs(t.exit_time),
    price:  t.exit_price,
    reason: t.exit_reason,
    pnl:    t.pnl,
    label:  `Exit (${t.exit_reason})`,
    direction: t.direction,
  }));

  // Y-axis domain: cover all SL and TP levels with a small pad
  const allPrices = trades.flatMap((t) => [t.sl_price, t.tp_price, t.entry_price, t.exit_price]);
  const yMin = Math.min(...allPrices);
  const yMax = Math.max(...allPrices);
  const pad  = (yMax - yMin) * 0.08 || 1;

  // X-axis domain
  const xMin = Math.min(...trades.map((t) => toMs(t.entry_time)));
  const xMax = Math.max(...trades.map((t) => toMs(t.exit_time)));
  const xPad = (xMax - xMin) * 0.02 || 3_600_000;

  return (
    <div aria-label="Trade map chart" role="img">
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart margin={{ top: 12, right: 24, left: 8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />

          <XAxis
            dataKey="time"
            type="number"
            scale="time"
            domain={[xMin - xPad, xMax + xPad]}
            tickFormatter={fmtDate}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            minTickGap={60}
          />

          <YAxis
            domain={[yMin - pad, yMax + pad]}
            tickFormatter={fmtPrice}
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={72}
          />

          <Tooltip content={<TradeTooltip />} />

          {/* ── Per-trade zone boxes ─────────────────────────────────────── */}
          {trades.map((t) => {
            const isLong  = t.direction === 1;
            const entryMs = toMs(t.entry_time);
            const exitMs  = toMs(t.exit_time);

            return (
              <React.Fragment key={t.id}>
                {/* Profit zone: entry → TP */}
                <ReferenceArea
                  x1={entryMs} x2={exitMs}
                  y1={isLong ? t.entry_price : t.tp_price}
                  y2={isLong ? t.tp_price    : t.entry_price}
                  fill={isLong ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)'}
                  stroke={isLong ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}
                  strokeWidth={1}
                />
                {/* Risk zone: entry → SL */}
                <ReferenceArea
                  x1={entryMs} x2={exitMs}
                  y1={isLong ? t.sl_price    : t.entry_price}
                  y2={isLong ? t.entry_price : t.sl_price}
                  fill={isLong ? 'rgba(239,68,68,0.12)' : 'rgba(34,197,94,0.12)'}
                  stroke={isLong ? 'rgba(239,68,68,0.25)' : 'rgba(34,197,94,0.25)'}
                  strokeWidth={1}
                />
                {/* Entry price horizontal line */}
                <ReferenceLine
                  segment={[
                    { x: entryMs, y: t.entry_price },
                    { x: exitMs,  y: t.entry_price },
                  ]}
                  stroke="rgba(255,255,255,0.25)"
                  strokeWidth={1}
                  strokeDasharray="3 3"
                />
              </React.Fragment>
            );
          })}

          {/* ── Entry markers ────────────────────────────────────────────── */}
          <Scatter
            data={entryPoints}
            dataKey="price"
            xAxisId={0}
            yAxisId={0}
            line={false}
            shape={(p: unknown) => <EntryDot {...(p as MarkerPayload)} />}
          />

          {/* ── Exit markers ─────────────────────────────────────────────── */}
          <Scatter
            data={exitPoints}
            dataKey="price"
            xAxisId={0}
            yAxisId={0}
            line={false}
            shape={(p: unknown) => <ExitDot {...(p as MarkerPayload)} />}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex items-center gap-5 mt-3 px-2 text-xs text-gray-500">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-green-500/20 border border-green-500/40" />
          Profit zone
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-red-500/20 border border-red-500/40" />
          Risk zone
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 12 12">
            <polygon points="6,1 11,11 1,11" fill="#22c55e" />
          </svg>
          Long entry
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 12 12">
            <polygon points="6,11 11,1 1,1" fill="#ef4444" />
          </svg>
          Short entry
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 12 12">
            <circle cx="6" cy="6" r="5" fill="#22c55e" />
          </svg>
          TP exit
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 12 12">
            <circle cx="6" cy="6" r="5" fill="#ef4444" />
          </svg>
          SL exit
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="12" height="12" viewBox="0 0 12 12">
            <circle cx="6" cy="6" r="5" fill="#6b7280" />
          </svg>
          EOD exit
        </span>
      </div>
    </div>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function ChartSkeleton({ height }: { height: number }) {
  return (
    <div
      className="bg-gray-700/40 rounded animate-pulse"
      style={{ height }}
      aria-label="Loading trade map"
    />
  );
}

// ─── Export ───────────────────────────────────────────────────────────────────

export default function TradeMapChart({ runId, height = 420 }: TradeMapChartProps) {
  const { data: trades = [], isLoading } = useQuery({
    queryKey: ['backtest-trades', runId],
    queryFn: () => getBacktestTrades(runId),
  });

  if (isLoading) return <ChartSkeleton height={height} />;
  return <Chart trades={trades} height={height} />;
}
