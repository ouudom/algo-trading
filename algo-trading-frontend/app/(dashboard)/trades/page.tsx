'use client';

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import PageHeader from '@/components/ui/PageHeader';
import TradeTable from '@/components/tables/TradeTable';
import { getTrades } from '@/lib/api';
import type { Trade } from '@/types';

// ─── Mock data ────────────────────────────────────────────────────────────────

const MOCK_TRADES: Trade[] = [
  {
    id: '1',
    symbol: 'AAPL',
    direction: 'LONG',
    status: 'CLOSED',
    entryPrice: 178.50,
    exitPrice: 185.20,
    quantity: 50,
    pnl: 335.00,
    pnlPct: 0.0375,
    entryDate: '2024-03-01T09:35:00Z',
    exitDate: '2024-03-05T14:22:00Z',
    strategy: 'MA Crossover',
    notes: null,
  },
  {
    id: '2',
    symbol: 'TSLA',
    direction: 'SHORT',
    status: 'CLOSED',
    entryPrice: 255.80,
    exitPrice: 241.30,
    quantity: 20,
    pnl: 290.00,
    pnlPct: 0.0567,
    entryDate: '2024-03-04T10:15:00Z',
    exitDate: '2024-03-08T11:45:00Z',
    strategy: 'Breakout',
    notes: null,
  },
  {
    id: '3',
    symbol: 'MSFT',
    direction: 'LONG',
    status: 'OPEN',
    entryPrice: 412.40,
    exitPrice: null,
    quantity: 30,
    pnl: null,
    pnlPct: null,
    entryDate: '2024-03-10T09:45:00Z',
    exitDate: null,
    strategy: 'MA Crossover',
    notes: null,
  },
  {
    id: '4',
    symbol: 'NVDA',
    direction: 'LONG',
    status: 'CLOSED',
    entryPrice: 620.00,
    exitPrice: 875.50,
    quantity: 15,
    pnl: 3832.50,
    pnlPct: 0.4121,
    entryDate: '2024-01-15T09:30:00Z',
    exitDate: '2024-03-01T15:55:00Z',
    strategy: 'MACD Divergence',
    notes: 'Held through earnings',
  },
  {
    id: '5',
    symbol: 'SPY',
    direction: 'LONG',
    status: 'CLOSED',
    entryPrice: 495.20,
    exitPrice: 488.70,
    quantity: 40,
    pnl: -260.00,
    pnlPct: -0.01313,
    entryDate: '2024-02-20T10:00:00Z',
    exitDate: '2024-02-22T11:30:00Z',
    strategy: 'RSI Mean Reversion',
    notes: null,
  },
  {
    id: '6',
    symbol: 'GOOG',
    direction: 'LONG',
    status: 'CLOSED',
    entryPrice: 140.25,
    exitPrice: 152.80,
    quantity: 60,
    pnl: 753.00,
    pnlPct: 0.0895,
    entryDate: '2024-02-05T09:35:00Z',
    exitDate: '2024-02-28T14:10:00Z',
    strategy: 'MA Crossover',
    notes: null,
  },
  {
    id: '7',
    symbol: 'META',
    direction: 'SHORT',
    status: 'CLOSED',
    entryPrice: 492.10,
    exitPrice: 510.45,
    quantity: 10,
    pnl: -183.50,
    pnlPct: -0.0373,
    entryDate: '2024-01-22T10:20:00Z',
    exitDate: '2024-01-26T15:45:00Z',
    strategy: 'Breakout',
    notes: 'Stopped out',
  },
  {
    id: '8',
    symbol: 'AMZN',
    direction: 'LONG',
    status: 'OPEN',
    entryPrice: 178.90,
    exitPrice: null,
    quantity: 45,
    pnl: null,
    pnlPct: null,
    entryDate: '2024-03-12T09:30:00Z',
    exitDate: null,
    strategy: 'MACD Divergence',
    notes: null,
  },
];

// ─── Filter types ─────────────────────────────────────────────────────────────

type StatusFilter = 'ALL' | Trade['status'];
type DirectionFilter = 'ALL' | Trade['direction'];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function TradesPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [directionFilter, setDirectionFilter] = useState<DirectionFilter>('ALL');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['trades', statusFilter, directionFilter],
    queryFn: () =>
      getTrades({
        pageSize: 100,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        direction: directionFilter !== 'ALL' ? directionFilter : undefined,
      }),
    placeholderData: {
      items: MOCK_TRADES,
      total: MOCK_TRADES.length,
      page: 1,
      pageSize: 100,
      totalPages: 1,
    },
  });

  // Client-side filter against mock data when backend unavailable
  const allTrades = data?.items ?? MOCK_TRADES;
  const filteredTrades = allTrades.filter((t) => {
    if (statusFilter !== 'ALL' && t.status !== statusFilter) return false;
    if (directionFilter !== 'ALL' && t.direction !== directionFilter) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Trade Journal"
        subtitle={`${filteredTrades.length} trade${filteredTrades.length !== 1 ? 's' : ''}`}
        actions={
          isError ? (
            <span className="text-xs text-yellow-500 bg-yellow-500/10 px-2 py-1 rounded border border-yellow-500/20">
              Showing sample data
            </span>
          ) : undefined
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap" role="group" aria-label="Trade filters">
        {/* Status filter */}
        <div className="flex items-center gap-1 bg-gray-900 border border-gray-800 rounded-md p-1">
          {(['ALL', 'OPEN', 'CLOSED', 'CANCELLED'] as StatusFilter[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                statusFilter === s
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              aria-pressed={statusFilter === s}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Direction filter */}
        <div className="flex items-center gap-1 bg-gray-900 border border-gray-800 rounded-md p-1">
          {(['ALL', 'LONG', 'SHORT'] as DirectionFilter[]).map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDirectionFilter(d)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                directionFilter === d
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              aria-pressed={directionFilter === d}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      <TradeTable data={filteredTrades} isLoading={isLoading} />
    </div>
  );
}
