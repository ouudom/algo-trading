'use client';

import React, { useState, useMemo, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getBacktests, deleteBacktest } from '@/lib/api';
import PageHeader from '@/components/ui/PageHeader';
import { formatPct, formatDate, cn } from '@/lib/utils';
import type { BacktestRun } from '@/types';

// ─── Strategy badge with config tooltip ───────────────────────────────────────

function StrategyBadge({ params }: { params?: Record<string, unknown> }) {
  const strategy = (params?.strategy as string) ?? 'ma_crossover';
  const isRsi = strategy === 'rsi_momentum';

  const lines: string[] = isRsi
    ? [
        `RSI Period: ${params?.rsi_period ?? 14}`,
        `RSI Threshold: ${params?.rsi_threshold ?? 50}`,
        `Trend EMA: ${params?.trend_ema_period ?? 200}`,
        `ATR Period: ${params?.atr_period ?? 14}`,
        `SL: ${params?.sl_multiplier ?? 1.5}× ATR`,
        `TP: ${params?.tp_multiplier ?? 3.0}× ATR`,
      ]
    : [
        `EMA Fast: ${params?.ema_fast ?? 20}`,
        `EMA Slow: ${params?.ema_slow ?? 50}`,
        `ATR Period: ${params?.atr_period ?? 14}`,
        `SL: ${params?.sl_multiplier ?? 1.5}× ATR`,
        `TP: ${params?.tp_multiplier ?? 3.0}× ATR`,
        params?.use_sma200_filter ? 'SMA(200) Filter: ON' : 'SMA(200) Filter: OFF',
      ];

  return (
    <div className="relative group inline-flex">
      <span
        className={cn(
          'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold cursor-default select-none',
          isRsi
            ? 'bg-purple-900/50 text-purple-300 border border-purple-700/50'
            : 'bg-blue-900/50 text-blue-300 border border-blue-700/50',
        )}
      >
        {isRsi ? 'RSI' : 'MA'}
      </span>
      {/* Tooltip */}
      <div className="absolute bottom-full left-0 mb-2 z-50 hidden group-hover:block pointer-events-none">
        <div className="bg-gray-900 border border-gray-700 rounded-lg shadow-xl px-3 py-2.5 w-44">
          <p className="text-xs font-semibold text-gray-300 mb-1.5">
            {isRsi ? 'RSI Momentum' : 'MA Crossover'}
          </p>
          <div className="space-y-0.5">
            {lines.map((line) => (
              <p key={line} className="text-xs text-gray-500">{line}</p>
            ))}
          </div>
        </div>
        {/* Arrow */}
        <div className="w-2 h-2 bg-gray-900 border-r border-b border-gray-700 rotate-45 mx-3 -mt-1" />
      </div>
    </div>
  );
}

// ─── Period cell helper ────────────────────────────────────────────────────────

function PeriodCell({ start, end }: { start: string | null; end: string | null }) {
  if (!start && !end) return <span className="text-gray-600">—</span>;
  const fmt = (d: string) => {
    const date = new Date(d);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };
  if (!end) return <span className="text-sm text-gray-500">{fmt(start!)}</span>;
  if (!start) return <span className="text-sm text-gray-500">{fmt(end)}</span>;

  // Same year: "Jan 2 – Mar 13, 2026"
  const startDate = new Date(start);
  const endDate = new Date(end);
  const sameYear = startDate.getFullYear() === endDate.getFullYear();
  const startStr = startDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', ...(sameYear ? {} : { year: 'numeric' }) });
  const endStr = endDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <span className="text-sm text-gray-500 tabular-nums whitespace-nowrap">
      {startStr} – {endStr}
    </span>
  );
}

// ─── Filter bar ───────────────────────────────────────────────────────────────

const selectCls =
  'bg-gray-800 border border-gray-700 rounded-md px-2.5 py-1.5 text-xs text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer';

interface Filters {
  symbol: string;
  timeframe: string;
  strategy: 'all' | 'ma_crossover' | 'rsi_momentum';
  returnFilter: 'all' | 'positive' | 'negative';
  minSharpe: string;
}

const DEFAULT_FILTERS: Filters = {
  symbol: '',
  timeframe: '',
  strategy: 'all',
  returnFilter: 'all',
  minSharpe: '',
};

function FilterBar({
  filters,
  onChange,
  onClear,
  symbols,
  timeframes,
  totalCount,
  filteredCount,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  onClear: () => void;
  symbols: string[];
  timeframes: string[];
  totalCount: number;
  filteredCount: number;
}) {
  const isActive =
    filters.symbol !== '' ||
    filters.timeframe !== '' ||
    filters.strategy !== 'all' ||
    filters.returnFilter !== 'all' ||
    filters.minSharpe !== '';

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Symbol */}
      <select
        value={filters.symbol}
        onChange={(e) => onChange({ ...filters, symbol: e.target.value })}
        className={selectCls}
        aria-label="Filter by symbol"
      >
        <option value="">All symbols</option>
        {symbols.map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>

      {/* Timeframe */}
      <select
        value={filters.timeframe}
        onChange={(e) => onChange({ ...filters, timeframe: e.target.value })}
        className={selectCls}
        aria-label="Filter by timeframe"
      >
        <option value="">All timeframes</option>
        {timeframes.map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>

      {/* Strategy */}
      <select
        value={filters.strategy}
        onChange={(e) => onChange({ ...filters, strategy: e.target.value as Filters['strategy'] })}
        className={selectCls}
        aria-label="Filter by strategy"
      >
        <option value="all">All strategies</option>
        <option value="ma_crossover">MA Crossover</option>
        <option value="rsi_momentum">RSI Momentum</option>
      </select>

      {/* Return direction */}
      <select
        value={filters.returnFilter}
        onChange={(e) =>
          onChange({ ...filters, returnFilter: e.target.value as Filters['returnFilter'] })
        }
        className={selectCls}
        aria-label="Filter by return direction"
      >
        <option value="all">All returns</option>
        <option value="positive">Positive only</option>
        <option value="negative">Negative only</option>
      </select>

      {/* Min Sharpe */}
      <div className="relative">
        <input
          type="number"
          step="0.1"
          placeholder="Min Sharpe"
          value={filters.minSharpe}
          onChange={(e) => onChange({ ...filters, minSharpe: e.target.value })}
          className={cn(selectCls, 'w-28 placeholder-gray-600')}
          aria-label="Minimum Sharpe ratio"
        />
      </div>

      {/* Clear */}
      {isActive && (
        <button
          onClick={onClear}
          className="text-xs text-gray-500 hover:text-gray-300 transition-colors px-1"
        >
          Clear
        </button>
      )}

      {/* Count */}
      <span className="ml-auto text-xs text-gray-600 tabular-nums">
        {isActive
          ? `${filteredCount} of ${totalCount}`
          : `${totalCount} run${totalCount !== 1 ? 's' : ''}`}
      </span>
    </div>
  );
}

// ─── Indeterminate checkbox ───────────────────────────────────────────────────

function IndeterminateCheckbox({
  checked,
  indeterminate,
  onChange,
  'aria-label': ariaLabel,
}: {
  checked: boolean;
  indeterminate: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  'aria-label'?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={onChange}
      aria-label={ariaLabel}
      className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900 cursor-pointer accent-blue-500"
    />
  );
}

// ─── Runs table ───────────────────────────────────────────────────────────────

function BacktestRunsTable() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkConfirm, setBulkConfirm] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);

  const [filters, setFilters] = useState<Filters>(() => {
    try {
      const saved = localStorage.getItem('backtests-filters');
      return saved ? { ...DEFAULT_FILTERS, ...JSON.parse(saved) } : DEFAULT_FILTERS;
    } catch {
      return DEFAULT_FILTERS;
    }
  });

  const updateFilters = (f: Filters) => {
    setFilters(f);
    setSelectedIds(new Set());
    try { localStorage.setItem('backtests-filters', JSON.stringify(f)); } catch { /* ignore */ }
  };

  const clearFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setSelectedIds(new Set());
    try { localStorage.removeItem('backtests-filters'); } catch { /* ignore */ }
  };

  const { data, isLoading } = useQuery({
    queryKey: ['backtests'],
    queryFn: () => getBacktests({ limit: 50 }),
  });

  async function handleBulkDelete() {
    setIsBulkDeleting(true);
    try {
      await Promise.all([...selectedIds].map((id) => deleteBacktest(id)));
      queryClient.invalidateQueries({ queryKey: ['backtests'] });
      setSelectedIds(new Set());
      setBulkConfirm(false);
    } finally {
      setIsBulkDeleting(false);
    }
  }

  const rows: BacktestRun[] = data ?? [];

  // Derive unique filter options from loaded data
  const symbols   = useMemo(() => [...new Set(rows.map((r) => r.symbol))].sort(),   [rows]);
  const timeframes = useMemo(() => [...new Set(rows.map((r) => r.timeframe))].sort(), [rows]);

  // Apply filters client-side
  const filtered = useMemo(() => rows.filter((r) => {
    if (filters.symbol    && r.symbol    !== filters.symbol)    return false;
    if (filters.timeframe && r.timeframe !== filters.timeframe) return false;
    if (filters.strategy !== 'all') {
      const rowStrategy = (r.params_json?.strategy as string) ?? 'ma_crossover';
      if (rowStrategy !== filters.strategy) return false;
    }
    if (filters.returnFilter === 'positive' && (r.total_return_pct ?? 0) <  0) return false;
    if (filters.returnFilter === 'negative' && (r.total_return_pct ?? 0) >= 0) return false;
    if (filters.minSharpe !== '' && (r.sharpe_ratio ?? 0) < Number(filters.minSharpe)) return false;
    return true;
  }), [rows, filters]);

  // Selection derived state
  const allFilteredSelected = filtered.length > 0 && filtered.every((r) => selectedIds.has(r.id));
  const someFilteredSelected = filtered.some((r) => selectedIds.has(r.id));

  function toggleSelectAll() {
    if (allFilteredSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((r) => r.id)));
    }
    setBulkConfirm(false);
  }

  function toggleRow(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setBulkConfirm(false);
  }

  // Count only ids that are in the current filtered set
  const selectedInView = filtered.filter((r) => selectedIds.has(r.id)).length;

  const colHeaders = [
    '', 'Symbol', 'Timeframe', 'Period', 'Strategy',
    'Total Return', 'Sharpe', 'Max DD',
    'Win Rate', 'Profit Factor', 'Trades',
  ];

  return (
    <div className="space-y-3">
      <FilterBar
        filters={filters}
        onChange={updateFilters}
        onClear={clearFilters}
        symbols={symbols}
        timeframes={timeframes}
        totalCount={rows.length}
        filteredCount={filtered.length}
      />

      {/* Bulk action bar */}
      {selectedInView > 0 && (
        <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700">
          <span className="text-xs text-gray-400 tabular-nums">
            {selectedInView} selected
          </span>
          <div className="h-3 w-px bg-gray-700" />
          {bulkConfirm ? (
            <span className="inline-flex items-center gap-2">
              <span className="text-xs text-red-400">
                Delete {selectedInView} run{selectedInView !== 1 ? 's' : ''}?
              </span>
              <button
                onClick={handleBulkDelete}
                disabled={isBulkDeleting}
                className="text-xs px-2.5 py-1 rounded bg-red-600 hover:bg-red-500 text-white font-medium transition-colors disabled:opacity-50"
              >
                {isBulkDeleting ? 'Deleting…' : 'Confirm'}
              </button>
              <button
                onClick={() => setBulkConfirm(false)}
                disabled={isBulkDeleting}
                className="text-xs px-2.5 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
              >
                Cancel
              </button>
            </span>
          ) : (
            <button
              onClick={() => setBulkConfirm(true)}
              className="text-xs px-2.5 py-1 rounded bg-red-900/60 hover:bg-red-800/80 border border-red-700/50 text-red-400 hover:text-red-300 font-medium transition-colors"
            >
              Delete selected
            </button>
          )}
          <button
            onClick={() => { setSelectedIds(new Set()); setBulkConfirm(false); }}
            className="ml-auto text-xs text-gray-600 hover:text-gray-400 transition-colors"
          >
            Deselect all
          </button>
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-gray-700">
        <div className="overflow-x-auto">
          <table
            className="w-full text-left border-collapse"
            aria-label="Backtest runs"
            aria-busy={isLoading}
          >
            <thead className="bg-gray-900 border-b border-gray-700">
              <tr>
                {/* Checkbox header */}
                <th className="px-4 py-3 w-10">
                  {!isLoading && filtered.length > 0 && (
                    <IndeterminateCheckbox
                      checked={allFilteredSelected}
                      indeterminate={!allFilteredSelected && someFilteredSelected}
                      onChange={toggleSelectAll}
                      aria-label="Select all rows"
                    />
                  )}
                </th>
                {colHeaders.slice(1).map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {isLoading
                ? Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i}>
                      {colHeaders.map((h) => (
                        <td key={h} className="px-4 py-3">
                          <div className="h-4 bg-gray-700/60 rounded animate-pulse w-3/4" />
                        </td>
                      ))}
                    </tr>
                  ))
                : filtered.length === 0
                ? (
                  <tr>
                    <td
                      colSpan={colHeaders.length}
                      className="px-4 py-10 text-center text-sm text-gray-600"
                    >
                      {rows.length === 0
                        ? <>No backtest runs yet — click <span className="text-gray-400">Run Test</span> to get started.</>
                        : 'No runs match the current filters.'}
                    </td>
                  </tr>
                )
                : filtered.map((r) => {
                    const done  = r.status === 'completed';
                    const retPos = (r.total_return_pct ?? 0) >= 0;
                    const isSelected = selectedIds.has(r.id);
                    return (
                      <tr
                        key={r.id}
                        onClick={() => router.push(`/backtests/${r.id}`)}
                        className={cn(
                          'hover:bg-gray-800/40 transition-colors duration-100 cursor-pointer',
                          isSelected && 'bg-blue-950/30',
                        )}
                      >
                        {/* Checkbox cell */}
                        <td
                          className="px-4 py-3 w-10"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleRow(r.id)}
                            aria-label={`Select backtest ${r.id}`}
                            className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900 cursor-pointer accent-blue-500"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono text-sm font-semibold text-gray-200">
                            {r.symbol}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono text-xs text-gray-400 bg-gray-800 border border-gray-700 px-1.5 py-0.5 rounded">
                            {r.timeframe}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <PeriodCell start={r.start_date} end={r.end_date} />
                        </td>
                        <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                          <StrategyBadge params={r.params_json} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          {done && r.total_return_pct != null ? (
                            <span className={cn('tabular-nums text-sm font-medium', retPos ? 'text-green-400' : 'text-red-400')}>
                              {retPos ? '+' : ''}{r.total_return_pct.toFixed(2)}%
                            </span>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {done && r.sharpe_ratio != null ? (
                            <span className="tabular-nums text-sm text-gray-300">
                              {r.sharpe_ratio.toFixed(2)}
                            </span>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {done && r.max_drawdown_pct != null ? (
                            <span className="tabular-nums text-sm text-red-400">
                              {formatPct(Math.abs(r.max_drawdown_pct) / 100)}
                            </span>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {done && r.win_rate != null ? (
                            <span className="tabular-nums text-sm text-gray-300">
                              {formatPct(r.win_rate)}
                            </span>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {done && r.profit_factor != null ? (
                            <span className="tabular-nums text-sm text-gray-300">
                              {r.profit_factor.toFixed(2)}
                            </span>
                          ) : done && r.profit_factor == null && r.win_rate === 1 ? (
                            <span className="tabular-nums text-sm text-gray-300">∞</span>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span className="tabular-nums text-sm text-gray-400">
                            {r.total_trades || '—'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function BacktestsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Backtests"
          subtitle="View and compare strategy backtest runs."
        />
        <Link
          href="/backtests/new"
          className="shrink-0 mt-1 inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Run Test
        </Link>
      </div>

      <BacktestRunsTable />
    </div>
  );
}
