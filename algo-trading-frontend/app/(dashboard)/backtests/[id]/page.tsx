'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getBacktestById, getBacktestEquity, getBacktestTrades, deleteBacktest } from '@/lib/api';
import MetricCard from '@/components/ui/MetricCard';
import EquityCurve from '@/components/charts/EquityCurve';
import { formatPct, formatDate, formatNumber, cn } from '@/lib/utils';
import CandleChart from '@/components/charts/CandleChart';
import type { EquityDataPoint, BacktestTrade } from '@/types';

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const lower = status.toLowerCase();
  const styles: Record<string, string> = {
    completed: 'bg-green-500/10 text-green-400 border-green-500/20',
    running:   'bg-blue-500/10  text-blue-400  border-blue-500/20',
    pending:   'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    failed:    'bg-red-500/10   text-red-400   border-red-500/20',
  };
  const cls = styles[lower] ?? 'bg-gray-700 text-gray-400 border-gray-600';
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border', cls)}>
      {status.toUpperCase()}
    </span>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('bg-gray-700/60 rounded animate-pulse', className)} />;
}

// ─── Configuration grid ───────────────────────────────────────────────────────

function ConfigCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">{label}</p>
      <p className="text-sm font-medium text-gray-200 tabular-nums">{value}</p>
    </div>
  );
}

function ConfigGrid({ params }: { params: Record<string, unknown> }) {
  const emaFast  = params.ema_fast        as number | undefined;
  const emaSlow  = params.ema_slow        as number | undefined;
  const atr      = params.atr_period      as number | undefined;
  const sl       = params.sl_multiplier   as number | undefined;
  const tp       = params.tp_multiplier   as number | undefined;
  const equity   = params.initial_equity  as number | undefined;
  const bePct    = params.be_trigger_pct  as number | undefined;
  const rr       = sl != null && tp != null && sl > 0 ? (tp / sl).toFixed(2) : null;

  const beValue =
    bePct != null && bePct > 0
      ? `${Math.round(bePct * 100)}% of TP`
      : 'Off';

  const cells: { label: string; value: string }[] = [
    { label: 'EMA Fast',       value: emaFast != null  ? String(emaFast)        : '—' },
    { label: 'EMA Slow',       value: emaSlow != null  ? String(emaSlow)        : '—' },
    { label: 'ATR Period',     value: atr     != null  ? String(atr)            : '—' },
    { label: 'SL Multiplier',  value: sl      != null  ? `${sl}×`               : '—' },
    { label: 'TP Multiplier',  value: tp      != null  ? `${tp}×`               : '—' },
    { label: 'RR Ratio',       value: rr      != null  ? `1 : ${rr}`            : '—' },
    { label: 'Break Even',     value: beValue },
    { label: 'Initial Equity', value: equity  != null  ? `$${equity.toLocaleString()}` : '—' },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {cells.map((c) => (
        <ConfigCell key={c.label} label={c.label} value={c.value} />
      ))}
    </div>
  );
}

// ─── Trades table ─────────────────────────────────────────────────────────────

function ExitReasonBadge({ reason }: { reason: string }) {
  const upper = reason.toUpperCase();
  const styles: Record<string, string> = {
    SL:  'bg-red-500/10 text-red-400 border-red-500/20',
    TP:  'bg-green-500/10 text-green-400 border-green-500/20',
    BE:  'bg-amber-500/10 text-amber-400 border-amber-500/20',
    EOD: 'bg-gray-700/50 text-gray-400 border-gray-600',
  };
  const cls = styles[upper] ?? 'bg-gray-700/50 text-gray-400 border-gray-600';
  return (
    <span className={cn('inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold border', cls)}>
      {upper}
    </span>
  );
}

function fmtDt(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function calcRR(t: BacktestTrade): string {
  const { entry_price, sl_price, tp_price, direction } = t;
  if (!entry_price || !sl_price || !tp_price) return '—';
  const risk   = Math.abs(entry_price - sl_price);
  const reward = Math.abs(tp_price   - entry_price);
  if (risk === 0) return '—';
  // Sanity-check: reward and risk should both be on the correct side
  if (direction === 1  && (sl_price >= entry_price || tp_price <= entry_price)) return '—';
  if (direction === -1 && (sl_price <= entry_price || tp_price >= entry_price)) return '—';
  return `${(reward / risk).toFixed(2)}×`;
}

const PAGE_SIZE = 50;

function TradesTable({ runId }: { runId: string }) {
  const { data: trades = [], isLoading } = useQuery({
    queryKey: ['backtest-trades', runId],
    queryFn: () => getBacktestTrades(runId),
  });

  const [page, setPage] = useState(0);

  useEffect(() => { setPage(0); }, [trades]);

  const sorted = [...trades].sort(
    (a, b) => new Date(b.entry_time).getTime() - new Date(a.entry_time).getTime()
  );
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const paginated = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const headers = [
    '#', 'Direction', 'Lots',
    'Entry Time', 'Entry', 'SL', 'TP', 'RR',
    'Exit Time', 'Exit', 'Reason', 'P&L',
  ];

  return (
    <div className="overflow-hidden rounded-lg border border-gray-700">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse" aria-label="Backtest trades">
          <thead className="bg-gray-900 border-b border-gray-700">
            <tr>
              {headers.map((h) => (
                <th key={h} className="px-3 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    {headers.map((h) => (
                      <td key={h} className="px-3 py-3">
                        <Skeleton className="h-4 w-3/4" />
                      </td>
                    ))}
                  </tr>
                ))
              : paginated.length === 0
              ? (
                <tr>
                  <td colSpan={headers.length} className="px-4 py-10 text-center text-sm text-gray-600">
                    No trades recorded
                  </td>
                </tr>
              )
              : paginated.map((t: BacktestTrade, i: number) => {
                  const isLong = t.direction === 1;
                  const pnlPos = t.pnl >= 0;
                  return (
                    <tr key={t.id} className="hover:bg-gray-800/30 transition-colors duration-100">
                      <td className="px-3 py-3 text-sm text-gray-500 tabular-nums">{page * PAGE_SIZE + i + 1}</td>
                      <td className="px-3 py-3">
                        <span className={cn(
                          'text-xs font-semibold px-1.5 py-0.5 rounded',
                          isLong ? 'bg-blue-500/10 text-blue-400' : 'bg-orange-500/10 text-orange-400'
                        )}>
                          {isLong ? 'LONG' : 'SHORT'}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-400 tabular-nums text-right">
                        {t.lots.toFixed(2)}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-400 tabular-nums whitespace-nowrap">
                        {fmtDt(t.entry_time)}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-300 tabular-nums text-right">
                        {t.entry_price.toFixed(4)}
                      </td>
                      <td className="px-3 py-3 text-sm text-red-400/80 tabular-nums text-right">
                        {t.sl_price.toFixed(4)}
                      </td>
                      <td className="px-3 py-3 text-sm text-green-400/80 tabular-nums text-right">
                        {t.tp_price.toFixed(4)}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-400 tabular-nums text-right">
                        {calcRR(t)}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-400 tabular-nums whitespace-nowrap">
                        {fmtDt(t.exit_time)}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-300 tabular-nums text-right">
                        {t.exit_price.toFixed(4)}
                      </td>
                      <td className="px-3 py-3">
                        <ExitReasonBadge reason={t.exit_reason} />
                      </td>
                      <td className={cn(
                        'px-3 py-3 text-sm font-medium tabular-nums text-right',
                        pnlPos ? 'text-green-400' : 'text-red-400'
                      )}>
                        {pnlPos ? '+' : ''}{t.pnl.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
          </tbody>
        </table>
      </div>
      {!isLoading && sorted.length > 0 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700 text-sm text-gray-400">
          <span>Page {page + 1} of {pageCount} · {sorted.length} trades</span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => p - 1)}
              disabled={page === 0}
              className="px-3 py-1 rounded bg-gray-800 border border-gray-700 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Prev
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page >= pageCount - 1}
              className="px-3 py-1 rounded bg-gray-800 border border-gray-700 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function BacktestDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.id as string;
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { mutate: doDelete, isPending: isDeleting } = useMutation({
    mutationFn: () => deleteBacktest(runId),
    onSuccess: () => router.replace('/backtests'),
  });

  const { data: run, isLoading: runLoading, isError } = useQuery({
    queryKey: ['backtest', runId],
    queryFn: () => getBacktestById(runId),
  });

  const { data: equityRaw, isLoading: equityLoading } = useQuery({
    queryKey: ['backtest-equity', runId],
    queryFn: () => getBacktestEquity(runId),
    enabled: !!run && run.status === 'completed',
  });

  React.useEffect(() => {
    if (isError) router.replace('/backtests');
  }, [isError, router]);

  const equityPoints: EquityDataPoint[] = (equityRaw?.points ?? []).map((p) => ({
    date: p.timestamp,
    equity: p.equity,
  }));

  // ── Metrics ──────────────────────────────────────────────────────────────

  const isCompleted = run?.status === 'completed';

  const retPct = run?.total_return_pct;
  const returnPct =
    retPct != null && isCompleted
      ? `${retPct >= 0 ? '+' : ''}${retPct.toFixed(2)}%`
      : '—';

  const sharpe = isCompleted && run?.sharpe_ratio != null
    ? formatNumber(run.sharpe_ratio, 2) : '—';

  const maxDd = isCompleted && run?.max_drawdown_pct != null
    ? formatPct(Math.abs(run.max_drawdown_pct) / 100) : '—';

  const winRate = isCompleted && run?.win_rate != null
    ? formatPct(run.win_rate) : '—';

  const pf =
    isCompleted && run?.profit_factor != null
      ? formatNumber(run.profit_factor, 2)
      : isCompleted && run?.profit_factor == null && run?.win_rate === 1
      ? '∞'
      : '—';

  const totalTrades = isCompleted ? (run?.total_trades?.toString() ?? '—') : '—';

  const returnPositive = (retPct ?? 0) >= 0;

  const returnUsd =
    isCompleted && run?.initial_equity != null && retPct != null
      ? run.initial_equity * (retPct / 100)
      : null;

  const maxDdUsd =
    isCompleted && run?.initial_equity != null && run?.max_drawdown_pct != null
      ? Math.abs(run.max_drawdown_pct / 100) * run.initial_equity
      : null;

  const fmtUsd = (n: number) =>
    `${n >= 0 ? '+' : '-'}$${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  // ── Date range label ────────────────────────────────────────────────────

  const dateRange =
    run?.start_date && run?.end_date
      ? `${formatDate(run.start_date)} – ${formatDate(run.end_date)}`
      : run?.created_at
      ? formatDate(run.created_at)
      : null;

  return (
    <div className="space-y-8">
      {/* Back nav + header */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <Link
            href="/backtests"
            className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Back to Backtests
          </Link>

          {run && (
            confirmDelete ? (
              <span className="inline-flex items-center gap-2">
                <span className="text-sm text-gray-400">Delete this run?</span>
                <button
                  onClick={() => doDelete()}
                  disabled={isDeleting}
                  className="text-sm px-3 py-1.5 rounded-md bg-red-600 hover:bg-red-500 text-white font-medium transition-colors"
                >
                  {isDeleting ? 'Deleting…' : 'Yes, delete'}
                </button>
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="text-sm px-3 py-1.5 rounded-md bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
                >
                  Cancel
                </button>
              </span>
            ) : (
              <button
                onClick={() => setConfirmDelete(true)}
                className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-red-400 transition-colors"
                aria-label="Delete backtest run"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Delete
              </button>
            )
          )}
        </div>

        <div className="flex flex-wrap items-start gap-3">
          {runLoading ? (
            <>
              <Skeleton className="h-8 w-40" />
              <Skeleton className="h-6 w-24" />
            </>
          ) : run ? (
            <>
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="text-2xl font-bold text-white">
                    {run.symbol}
                  </h1>
                  <span className="text-sm font-medium text-gray-400 bg-gray-800 border border-gray-700 px-2 py-0.5 rounded">
                    {run.timeframe}
                  </span>
                  <StatusBadge status={run.status} />
                </div>
                {dateRange && (
                  <p className="text-sm text-gray-500 mt-1">{dateRange}</p>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>

      {/* Metrics */}
      <section aria-labelledby="section-metrics">
        <h2 id="section-metrics" className="text-lg font-semibold text-white mb-4">Performance</h2>
        {runLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <MetricCard
              label="Total Return"
              value={returnPct}
              accent={returnPositive ? 'green' : 'red'}
              deltaPositive={returnPositive}
              sublabel={returnUsd != null ? fmtUsd(returnUsd) : undefined}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={sharpe}
              accent={(run?.sharpe_ratio ?? 0) >= 1 ? 'green' : 'yellow'}
            />
            <MetricCard
              label="Max Drawdown"
              value={maxDd}
              accent="red"
              deltaPositive={false}
              sublabel={maxDdUsd != null ? `-$${maxDdUsd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : undefined}
            />
            <MetricCard
              label="Win Rate"
              value={winRate}
              accent={(run?.win_rate ?? 0) >= 0.4 ? 'green' : 'yellow'}
            />
            <MetricCard
              label="Profit Factor"
              value={pf}
              accent={(run?.profit_factor ?? 0) >= 1.3 ? 'green' : 'yellow'}
            />
            <MetricCard
              label="Total Trades"
              value={totalTrades}
              accent="blue"
            />
          </div>
        )}
      </section>

      {/* Configuration */}
      {run?.params_json && (
        <section aria-labelledby="section-config">
          <h2 id="section-config" className="text-lg font-semibold text-white mb-4">Configuration</h2>
          <ConfigGrid params={run.params_json} />
        </section>
      )}

      {/* Equity curve */}
      {isCompleted && (
        <section aria-labelledby="section-equity">
          <h2 id="section-equity" className="text-lg font-semibold text-white mb-4">Equity Curve</h2>
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            {equityLoading ? (
              <Skeleton className="h-72" />
            ) : (
              <EquityCurve data={equityPoints} height={288} />
            )}
          </div>
        </section>
      )}

      {/* Trades */}
      {isCompleted && (
        <section aria-labelledby="section-trades">
          <h2 id="section-trades" className="text-lg font-semibold text-white mb-4">Trades</h2>
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 mb-6">
            <CandleChart runId={runId} height={480} />
          </div>
          <TradesTable runId={runId} />
        </section>
      )}
    </div>
  );
}
