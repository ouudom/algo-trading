'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBacktestById, getBacktestEquity } from '@/lib/api';
import MetricCard from '@/components/ui/MetricCard';
import EquityCurve from '@/components/charts/EquityCurve';
import type { EquityDataPoint } from '@/types';
import { formatPct, formatNumber } from '@/lib/utils';

interface BacktestResultPanelProps {
  runId: string;
}

export default function BacktestResultPanel({
  runId,
}: BacktestResultPanelProps) {
  const { data: run, isLoading: runLoading } = useQuery({
    queryKey: ['backtest', runId],
    queryFn: () => getBacktestById(runId),
  });

  const { data: equityRaw, isLoading: equityLoading } = useQuery({
    queryKey: ['backtest-equity', runId],
    queryFn: () => getBacktestEquity(runId),
  });

  const isLoading = runLoading || equityLoading;

  const equityPoints: EquityDataPoint[] = (equityRaw?.points ?? []).map((p) => ({
    date: p.timestamp,
    equity: p.equity,
  }));

  if (isLoading) {
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
        <div className="grid grid-cols-3 gap-4 mb-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-20 bg-gray-700/40 rounded-lg animate-pulse" />
          ))}
        </div>
        <div className="h-64 bg-gray-700/40 rounded-lg animate-pulse" />
      </div>
    );
  }

  if (!run) return null;

  const isCompleted = run.status === 'completed';

  const retPct = run.total_return_pct;
  const returnPct =
    retPct != null && isCompleted
      ? `${retPct >= 0 ? '+' : ''}${retPct.toFixed(2)}%`
      : '—';

  const sharpe = isCompleted && run.sharpe_ratio != null ? formatNumber(run.sharpe_ratio, 2) : '—';
  const maxDd = isCompleted && run.max_drawdown_pct != null ? formatPct(Math.abs(run.max_drawdown_pct) / 100) : '—';
  const winRate = isCompleted && run.win_rate != null ? formatPct(run.win_rate) : '—';
  const pf =
    isCompleted && run.profit_factor != null
      ? formatNumber(run.profit_factor, 2)
      : isCompleted && run.profit_factor == null && run.win_rate === 1
      ? '∞'
      : '—';
  const trades = isCompleted ? run.total_trades.toString() : '—';

  const returnPositive = (retPct ?? 0) >= 0;

  return (
    <div
      className="bg-gray-800 border border-gray-700 rounded-xl p-6 transition-opacity duration-500 opacity-100"
    >
      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
        <MetricCard
          label="Total Return"
          value={returnPct}
          accent={returnPositive ? 'green' : 'red'}
          deltaPositive={returnPositive}
        />
        <MetricCard
          label="Sharpe Ratio"
          value={sharpe}
          accent={(run.sharpe_ratio ?? 0) >= 1 ? 'green' : 'yellow'}
        />
        <MetricCard
          label="Max Drawdown"
          value={maxDd}
          accent="red"
          deltaPositive={false}
        />
        <MetricCard
          label="Win Rate"
          value={winRate}
          accent={(run.win_rate ?? 0) >= 0.4 ? 'green' : 'yellow'}
        />
        <MetricCard
          label="Profit Factor"
          value={pf}
          accent={(run.profit_factor ?? 0) >= 1.3 ? 'green' : 'yellow'}
        />
        <MetricCard
          label="Total Trades"
          value={trades}
          accent="blue"
        />
      </div>

      {/* Equity curve */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
          Equity Curve
        </p>
        <EquityCurve data={equityPoints} height={280} />
      </div>
    </div>
  );
}
