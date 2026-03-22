'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import PageHeader from '@/components/ui/PageHeader';
import MetricCard from '@/components/ui/MetricCard';
import DrawdownChart from '@/components/charts/DrawdownChart';
import { getAnalytics, getAnalyticsDrawdown } from '@/lib/api';
import { formatCurrency, formatPct } from '@/lib/utils';
import type { AnalyticsMetrics, DrawdownDataPoint } from '@/types';

// ─── Mock data ────────────────────────────────────────────────────────────────

const MOCK_METRICS: AnalyticsMetrics = {
  totalReturn: 15_480.25,
  totalReturnPct: 0.1548,
  sharpeRatio: 1.87,
  sortinoRatio: 2.43,
  maxDrawdown: -8230.40,
  maxDrawdownPct: -0.0823,
  winRate: 0.634,
  profitFactor: 2.12,
  totalTrades: 142,
  winningTrades: 90,
  losingTrades: 52,
  avgWin: 412.80,
  avgLoss: -198.40,
  avgHoldingDays: 4.7,
  bestTrade: 3832.50,
  worstTrade: -640.00,
};

const MOCK_DRAWDOWN: DrawdownDataPoint[] = Array.from({ length: 90 }, (_, i) => {
  const t = i / 89;
  // Simulate a realistic drawdown profile
  const d1 = -0.04 * Math.sin(t * Math.PI * 2);
  const d2 = -0.06 * Math.sin(t * Math.PI * 3.5 + 1);
  const noise = (Math.random() - 0.5) * 0.01;
  const drawdown = Math.min(0, d1 + d2 + noise);
  const date = new Date(2024, 0, 1 + i);
  return {
    date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    drawdown: parseFloat(drawdown.toFixed(4)),
  };
});

// ─── Section wrapper ──────────────────────────────────────────────────────────

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-label={title}>
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
        {title}
      </h2>
      {children}
    </section>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const {
    data: metrics,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['analytics'],
    queryFn: () => getAnalytics(),
    placeholderData: MOCK_METRICS,
  });

  const { data: drawdownData, isLoading: ddLoading } = useQuery({
    queryKey: ['analytics-drawdown'],
    queryFn: () => getAnalyticsDrawdown(),
    placeholderData: MOCK_DRAWDOWN,
  });

  const m = metrics ?? MOCK_METRICS;
  const dd = drawdownData ?? MOCK_DRAWDOWN;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Analytics"
        subtitle="Portfolio performance metrics and risk analysis"
        actions={
          isError ? (
            <span className="text-xs text-yellow-500 bg-yellow-500/10 px-2 py-1 rounded border border-yellow-500/20">
              Showing sample data
            </span>
          ) : undefined
        }
      />

      {/* Returns & risk ratio row */}
      <Section title="Returns">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <MetricCard
            label="Total Return"
            value={isLoading ? '...' : formatCurrency(m.totalReturn)}
            delta={isLoading ? undefined : formatPct(m.totalReturnPct)}
            deltaPositive={m.totalReturn >= 0}
            accent={m.totalReturn >= 0 ? 'green' : 'red'}
          />
          <MetricCard
            label="Sharpe Ratio"
            value={isLoading ? '...' : m.sharpeRatio.toFixed(2)}
            sublabel="risk-adjusted return"
            accent={m.sharpeRatio >= 1.5 ? 'green' : m.sharpeRatio >= 1 ? 'yellow' : 'red'}
          />
          <MetricCard
            label="Sortino Ratio"
            value={isLoading ? '...' : m.sortinoRatio.toFixed(2)}
            sublabel="downside risk-adjusted"
            accent={m.sortinoRatio >= 2 ? 'green' : m.sortinoRatio >= 1 ? 'yellow' : 'red'}
          />
          <MetricCard
            label="Profit Factor"
            value={isLoading ? '...' : m.profitFactor.toFixed(2)}
            sublabel="gross win / gross loss"
            accent={m.profitFactor >= 2 ? 'green' : m.profitFactor >= 1 ? 'yellow' : 'red'}
          />
        </div>
      </Section>

      {/* Risk & drawdown */}
      <Section title="Risk">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <MetricCard
            label="Max Drawdown $"
            value={isLoading ? '...' : formatCurrency(m.maxDrawdown)}
            accent="red"
          />
          <MetricCard
            label="Max Drawdown %"
            value={isLoading ? '...' : formatPct(m.maxDrawdownPct)}
            accent="red"
          />
          <MetricCard
            label="Best Trade"
            value={isLoading ? '...' : formatCurrency(m.bestTrade)}
            accent="green"
          />
          <MetricCard
            label="Worst Trade"
            value={isLoading ? '...' : formatCurrency(m.worstTrade)}
            accent="red"
          />
        </div>
      </Section>

      {/* Drawdown chart */}
      <Section title="Drawdown Over Time">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <p className="text-xs text-gray-500 mb-4">
            Percentage drawdown from the rolling equity peak
          </p>
          <DrawdownChart data={dd} height={220} />
        </div>
      </Section>

      {/* Trade statistics */}
      <Section title="Trade Statistics">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
          <MetricCard
            label="Win Rate"
            value={isLoading ? '...' : formatPct(m.winRate)}
            sublabel={isLoading ? '' : `${m.winningTrades}W / ${m.losingTrades}L`}
            accent={m.winRate >= 0.5 ? 'green' : 'red'}
          />
          <MetricCard
            label="Total Trades"
            value={isLoading ? '...' : m.totalTrades.toLocaleString()}
            accent="none"
          />
          <MetricCard
            label="Avg Win"
            value={isLoading ? '...' : formatCurrency(m.avgWin)}
            accent="green"
          />
          <MetricCard
            label="Avg Loss"
            value={isLoading ? '...' : formatCurrency(m.avgLoss)}
            accent="red"
          />
          <MetricCard
            label="Win/Loss Ratio"
            value={
              isLoading
                ? '...'
                : (m.avgWin / Math.abs(m.avgLoss)).toFixed(2)
            }
            sublabel="avg win ÷ avg loss"
            accent={m.avgWin / Math.abs(m.avgLoss) >= 1.5 ? 'green' : 'yellow'}
          />
          <MetricCard
            label="Avg Hold"
            value={isLoading ? '...' : `${m.avgHoldingDays.toFixed(1)}d`}
            sublabel="average holding days"
            accent="none"
          />
        </div>
      </Section>
    </div>
  );
}
