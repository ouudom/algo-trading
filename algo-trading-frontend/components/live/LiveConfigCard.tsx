'use client';

import React from 'react';
import type { LiveTradingConfig } from '@/types';
import { cn } from '@/lib/utils';

interface LiveConfigCardProps {
  config: LiveTradingConfig;
  openCount?: number;
  todayPnl?: number;
  onEnable: (id: string) => void;
  onDisable: (id: string) => void;
  onDelete: (id: string) => void;
  onViewTrades: (config: LiveTradingConfig) => void;
  isLoading?: boolean;
}

const STATUS_STYLES: Record<string, { dot: string; text: string; label: string }> = {
  idle:             { dot: 'bg-gray-500',  text: 'text-gray-400',  label: 'Idle' },
  running:          { dot: 'bg-green-500', text: 'text-green-400', label: 'Running' },
  halted_daily:     { dot: 'bg-amber-500', text: 'text-amber-400', label: 'Halted — Daily Limit' },
  halted_drawdown:  { dot: 'bg-red-500',   text: 'text-red-400',   label: 'Halted — Drawdown' },
  error:            { dot: 'bg-red-500',   text: 'text-red-400',   label: 'Error' },
};

const SIGNAL_LABELS: Record<number, { label: string; color: string }> = {
  1:  { label: 'LONG',  color: 'text-green-400' },
  [-1]: { label: 'SHORT', color: 'text-red-400' },
  0:  { label: 'Flat',  color: 'text-gray-500' },
};

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
    hour12: false, timeZone: 'UTC',
  }) + ' UTC';
}

function formatPnl(pnl: number): string {
  const abs = Math.abs(pnl).toFixed(2);
  return pnl >= 0 ? `+$${abs}` : `-$${abs}`;
}

export default function LiveConfigCard({
  config,
  openCount = 0,
  todayPnl = 0,
  onEnable,
  onDisable,
  onDelete,
  onViewTrades,
  isLoading = false,
}: LiveConfigCardProps) {
  const statusStyle = STATUS_STYLES[config.status] ?? STATUS_STYLES.idle;
  const signalInfo = config.last_signal !== null && config.last_signal !== undefined
    ? (SIGNAL_LABELS[config.last_signal] ?? { label: String(config.last_signal), color: 'text-gray-400' })
    : null;

  const pnlColor = todayPnl > 0 ? 'text-green-400' : todayPnl < 0 ? 'text-red-400' : 'text-gray-400';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-gray-100 font-semibold text-base">
              {config.symbol}
            </span>
            <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-blue-600/20 text-blue-400 border border-blue-500/20">
              {config.variation}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">{config.strategy}</p>
        </div>

        {/* Status badge */}
        <div className={cn('flex items-center gap-1.5 text-xs font-medium', statusStyle.text)}>
          <span className={cn('w-2 h-2 rounded-full shrink-0', statusStyle.dot)} />
          {statusStyle.label}
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3 text-xs">
        <div>
          <p className="text-gray-600 uppercase tracking-wide mb-0.5">Last bar</p>
          <p className="text-gray-300">{formatTime(config.last_run_at)}</p>
        </div>
        <div>
          <p className="text-gray-600 uppercase tracking-wide mb-0.5">Last signal</p>
          {signalInfo ? (
            <p className={cn('font-medium', signalInfo.color)}>{signalInfo.label}</p>
          ) : (
            <p className="text-gray-500">—</p>
          )}
        </div>
        <div>
          <p className="text-gray-600 uppercase tracking-wide mb-0.5">Open positions</p>
          <p className="text-gray-300">{openCount}</p>
        </div>
        <div className="col-span-2">
          <p className="text-gray-600 uppercase tracking-wide mb-0.5">Today PnL</p>
          <p className={cn('font-medium', pnlColor)}>{formatPnl(todayPnl)}</p>
        </div>
      </div>

      {/* Error message */}
      {config.status === 'error' && config.last_error && (
        <p className="text-xs text-red-400 bg-red-900/20 border border-red-800/30 rounded px-3 py-2 truncate">
          {config.last_error}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        {config.enabled ? (
          <button
            onClick={() => onDisable(config.id)}
            disabled={isLoading}
            className="flex-1 text-xs font-medium py-1.5 px-3 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-700 disabled:opacity-50 transition-colors"
          >
            Disable
          </button>
        ) : (
          <button
            onClick={() => onEnable(config.id)}
            disabled={isLoading}
            className="flex-1 text-xs font-medium py-1.5 px-3 rounded bg-green-700/30 text-green-400 hover:bg-green-700/50 border border-green-600/30 disabled:opacity-50 transition-colors"
          >
            Enable
          </button>
        )}

        <button
          onClick={() => onViewTrades(config)}
          className="text-xs font-medium py-1.5 px-3 rounded bg-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-700 border border-gray-700 transition-colors"
        >
          View Trades
        </button>

        <button
          onClick={() => {
            if (confirm(`Delete config for ${config.symbol} ${config.variation}?`)) {
              onDelete(config.id);
            }
          }}
          disabled={isLoading || config.enabled}
          title={config.enabled ? 'Disable before deleting' : 'Delete'}
          className="text-xs font-medium py-1.5 px-3 rounded bg-gray-800 text-red-500 hover:bg-red-900/30 hover:text-red-400 border border-gray-700 disabled:opacity-30 transition-colors"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
