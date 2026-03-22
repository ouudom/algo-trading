'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import PageHeader from '@/components/ui/PageHeader';
import MetricCard from '@/components/ui/MetricCard';
import EquityCurve from '@/components/charts/EquityCurve';
import { getDashboardSummary } from '@/lib/api';
import { formatCurrency, formatPct, signOf } from '@/lib/utils';

// ─── Mock / fallback data used when the backend is not running ────────────────

const MOCK_EQUITY: { date: string; equity: number }[] = Array.from(
  { length: 90 },
  (_, i) => {
    const date = new Date(2024, 0, 1 + i);
    const noise = (Math.random() - 0.45) * 1200;
    const trend = i * 60;
    return {
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      equity: Math.round(100_000 + trend + noise),
    };
  }
);

export default function HomePage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: getDashboardSummary,
    // Provide mock data so the page renders without a backend
    placeholderData: {
      accountEquity: 105_480.25,
      dailyPnl: 1_234.56,
      dailyPnlPct: 0.0118,
      openPositions: 3,
      totalTrades: 142,
      winRate: 0.634,
      equityCurve: MOCK_EQUITY,
    },
  });

  const equityCurve = data?.equityCurve ?? MOCK_EQUITY;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle="Equity overview and key account metrics"
      />

      {/* Key metrics row */}
      <section aria-label="Key metrics" className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5">
        <MetricCard
          label="Account Equity"
          value={isLoading ? '...' : formatCurrency(data?.accountEquity ?? 0)}
          accent="blue"
        />
        <MetricCard
          label="Daily P&L"
          value={
            isLoading
              ? '...'
              : `${signOf(data?.dailyPnl ?? 0)}${formatCurrency(data?.dailyPnl ?? 0)}`
          }
          delta={
            isLoading
              ? undefined
              : `${signOf(data?.dailyPnlPct ?? 0)}${formatPct(data?.dailyPnlPct ?? 0)}`
          }
          deltaPositive={(data?.dailyPnl ?? 0) >= 0}
          accent={(data?.dailyPnl ?? 0) >= 0 ? 'green' : 'red'}
        />
        <MetricCard
          label="Open Positions"
          value={isLoading ? '...' : (data?.openPositions ?? 0)}
          accent="none"
        />
        <MetricCard
          label="Total Trades"
          value={isLoading ? '...' : (data?.totalTrades ?? 0).toLocaleString()}
          accent="none"
        />
        <MetricCard
          label="Win Rate"
          value={isLoading ? '...' : formatPct(data?.winRate ?? 0)}
          accent={(data?.winRate ?? 0) >= 0.5 ? 'green' : 'red'}
        />
      </section>

      {/* Equity curve card */}
      <section aria-label="Equity curve">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-gray-300">Equity Curve</h2>
              <p className="text-xs text-gray-500 mt-0.5">Cumulative account value over time</p>
            </div>
            {isError && (
              <span className="text-xs text-yellow-500 bg-yellow-500/10 px-2 py-1 rounded border border-yellow-500/20">
                Showing sample data
              </span>
            )}
          </div>

          <EquityCurve
            data={equityCurve}
            height={300}
            initialEquity={equityCurve[0]?.equity}
          />
        </div>
      </section>

      {/* Recent activity placeholder */}
      <section aria-label="Recent activity">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">Recent Activity</h2>
          <div className="space-y-2">
            {[
              { action: 'BUY AAPL 50 @ $182.50', time: '2 min ago', type: 'buy' },
              { action: 'SELL TSLA 20 @ $248.30', time: '14 min ago', type: 'sell' },
              { action: 'BUY MSFT 30 @ $415.20', time: '1 hr ago', type: 'buy' },
              { action: 'Backtest "MA Crossover" completed', time: '3 hrs ago', type: 'info' },
            ].map((item, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2 border-b border-gray-800/60 last:border-0"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                      item.type === 'buy'
                        ? 'bg-green-400'
                        : item.type === 'sell'
                        ? 'bg-red-400'
                        : 'bg-blue-400'
                    }`}
                    aria-hidden="true"
                  />
                  <span className="text-sm text-gray-300">{item.action}</span>
                </div>
                <span className="text-xs text-gray-600 ml-4 shrink-0">{item.time}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
