'use client';

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getLiveConfigs,
  getLiveStats,
  getLiveTrades,
  createLiveConfig,
  enableLiveConfig,
  disableLiveConfig,
  deleteLiveConfig,
} from '@/lib/api';
import type { LiveTradingConfig, LiveTrade } from '@/types';
import LiveConfigCard from '@/components/live/LiveConfigCard';

// ─── Supported symbols / variations from strategy catalogue ──────────────────

const SYMBOLS = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'];
const VARIATIONS = ['V1', 'V2', 'V3', 'V4', 'V5'];

// ─── Add Config Modal ─────────────────────────────────────────────────────────

function AddConfigModal({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (symbol: string, variation: string) => void;
}) {
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [variation, setVariation] = useState(VARIATIONS[0]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
        <h2 className="text-gray-100 font-semibold text-lg mb-4">Add Strategy</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Symbol</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {SYMBOLS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Variation</label>
            <select
              value={variation}
              onChange={(e) => setVariation(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {VARIATIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-md text-sm font-medium bg-gray-800 text-gray-400 hover:bg-gray-700 border border-gray-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onAdd(symbol, variation);
              onClose();
            }}
            className="flex-1 py-2 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-500 transition-colors"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Trades Drawer ────────────────────────────────────────────────────────────

function TradesDrawer({
  config,
  onClose,
}: {
  config: LiveTradingConfig;
  onClose: () => void;
}) {
  const { data: trades = [], isLoading } = useQuery({
    queryKey: ['liveTrades', config.symbol],
    queryFn: () => getLiveTrades({ symbol: config.symbol, limit: 50 }),
  });

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50">
      <div className="bg-gray-900 border-l border-gray-800 w-full max-w-lg h-full flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 shrink-0">
          <div>
            <h2 className="text-gray-100 font-semibold">
              {config.symbol} {config.variation} — Trades
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">{config.strategy}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-200 transition-colors p-1"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Trade list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {isLoading && (
            <p className="text-gray-500 text-sm text-center py-8">Loading trades…</p>
          )}
          {!isLoading && trades.length === 0 && (
            <p className="text-gray-500 text-sm text-center py-8">No trades yet.</p>
          )}
          {trades.map((t: LiveTrade) => {
            const isLong = t.direction === 1;
            const pnlColor = t.pnl !== null
              ? t.pnl >= 0 ? 'text-green-400' : 'text-red-400'
              : 'text-gray-500';
            const statusColor = t.status === 'open' ? 'text-green-400' : 'text-gray-400';

            return (
              <div key={t.id} className="bg-gray-800 rounded-lg px-4 py-3 text-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={isLong ? 'text-green-400 font-medium' : 'text-red-400 font-medium'}>
                      {isLong ? 'LONG' : 'SHORT'}
                    </span>
                    <span className="text-gray-500">{t.lots} lots</span>
                    <span className={cn('capitalize', statusColor)}>{t.status}</span>
                  </div>
                  {t.pnl !== null && (
                    <span className={cn('font-medium', pnlColor)}>
                      {t.pnl >= 0 ? '+' : ''}{t.pnl.toFixed(2)}
                    </span>
                  )}
                </div>
                <div className="flex gap-4 text-gray-500">
                  <span>Entry: {t.entry_price.toFixed(5)}</span>
                  {t.exit_price !== null && <span>Exit: {t.exit_price.toFixed(5)}</span>}
                  {t.exit_reason && <span className="uppercase">{t.exit_reason}</span>}
                </div>
                <div className="text-gray-600">
                  Ticket #{t.ticket} · {new Date(t.entry_time).toLocaleString('en-US', { timeZone: 'UTC' })} UTC
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function cn(...classes: (string | undefined | false)[]): string {
  return classes.filter(Boolean).join(' ');
}

// ─── Stats bar ────────────────────────────────────────────────────────────────

function StatsBar() {
  const { data: stats } = useQuery({
    queryKey: ['liveStats'],
    queryFn: getLiveStats,
    refetchInterval: 30_000,
  });

  if (!stats) return null;

  const pnlColor = stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400';
  const todayColor = stats.today_pnl >= 0 ? 'text-green-400' : 'text-red-400';

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {[
        { label: 'Open Positions', value: String(stats.open_count) },
        { label: 'Total Trades', value: String(stats.total_trades) },
        {
          label: 'Total PnL',
          value: (stats.total_pnl >= 0 ? '+' : '') + `$${Math.abs(stats.total_pnl).toFixed(2)}`,
          color: pnlColor,
        },
        {
          label: "Today's PnL",
          value: (stats.today_pnl >= 0 ? '+' : '') + `$${Math.abs(stats.today_pnl).toFixed(2)}`,
          color: todayColor,
        },
      ].map((stat) => (
        <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-3">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{stat.label}</p>
          <p className={cn('text-xl font-semibold', stat.color ?? 'text-gray-100')}>{stat.value}</p>
        </div>
      ))}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LiveTradingPage() {
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [viewTradesConfig, setViewTradesConfig] = useState<LiveTradingConfig | null>(null);

  const { data: configs = [], isLoading } = useQuery({
    queryKey: ['liveConfigs'],
    queryFn: getLiveConfigs,
    refetchInterval: 30_000,
  });

  const { data: openPositions = [] } = useQuery({
    queryKey: ['liveOpenPositions'],
    queryFn: () => getLiveTrades({ status: 'open' }),
    refetchInterval: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: ({ symbol, variation }: { symbol: string; variation: string }) =>
      createLiveConfig(symbol, variation),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['liveConfigs'] }),
    onError: (err: Error) => alert(`Failed to create: ${err.message}`),
  });

  const enableMutation = useMutation({
    mutationFn: enableLiveConfig,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['liveConfigs'] }),
    onError: (err: Error) => alert(`Failed to enable: ${err.message}`),
  });

  const disableMutation = useMutation({
    mutationFn: disableLiveConfig,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['liveConfigs'] }),
    onError: (err: Error) => alert(`Failed to disable: ${err.message}`),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLiveConfig,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['liveConfigs'] }),
    onError: (err: Error) => alert(`Failed to delete: ${err.message}`),
  });

  const isMutating =
    createMutation.isPending ||
    enableMutation.isPending ||
    disableMutation.isPending ||
    deleteMutation.isPending;

  // Count open positions per symbol
  const openCountBySymbol: Record<string, number> = {};
  for (const t of openPositions as LiveTrade[]) {
    openCountBySymbol[t.symbol] = (openCountBySymbol[t.symbol] ?? 0) + 1;
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Live Trading</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Manage live Exness strategies. Each enabled config runs at H1 bar close.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Strategy
        </button>
      </div>

      {/* Stats bar */}
      <StatsBar />

      {/* Config cards */}
      {isLoading && (
        <div className="text-center py-16 text-gray-500 text-sm">Loading configurations…</div>
      )}

      {!isLoading && configs.length === 0 && (
        <div className="text-center py-16 border border-dashed border-gray-800 rounded-xl">
          <p className="text-gray-500 text-sm">No strategies configured yet.</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="mt-3 text-blue-400 text-sm hover:text-blue-300 underline underline-offset-2"
          >
            Add your first strategy
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {configs.map((config: LiveTradingConfig) => (
          <LiveConfigCard
            key={config.id}
            config={config}
            openCount={openCountBySymbol[config.symbol] ?? 0}
            todayPnl={0}
            onEnable={(id) => enableMutation.mutate(id)}
            onDisable={(id) => disableMutation.mutate(id)}
            onDelete={(id) => deleteMutation.mutate(id)}
            onViewTrades={(c) => setViewTradesConfig(c)}
            isLoading={isMutating}
          />
        ))}
      </div>

      {/* Modals */}
      {showAddModal && (
        <AddConfigModal
          onClose={() => setShowAddModal(false)}
          onAdd={(symbol, variation) => createMutation.mutate({ symbol, variation })}
        />
      )}

      {viewTradesConfig && (
        <TradesDrawer
          config={viewTradesConfig}
          onClose={() => setViewTradesConfig(null)}
        />
      )}
    </div>
  );
}
