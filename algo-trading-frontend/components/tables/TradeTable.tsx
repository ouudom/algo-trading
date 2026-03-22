'use client';

import React, { useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
  type ColumnFiltersState,
  type PaginationState,
} from '@tanstack/react-table';
import type { Trade } from '@/types';
import { formatCurrency, formatPct, formatDate, cn } from '@/lib/utils';

interface TradeTableProps {
  data: Trade[];
  isLoading?: boolean;
}

const columnHelper = createColumnHelper<Trade>();

// Direction badge
function DirectionBadge({ direction }: { direction: Trade['direction'] }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold',
        direction === 'LONG'
          ? 'bg-green-500/10 text-green-400'
          : 'bg-red-500/10 text-red-400'
      )}
    >
      {direction}
    </span>
  );
}

// Status badge
function StatusBadge({ status }: { status: Trade['status'] }) {
  const styles: Record<Trade['status'], string> = {
    OPEN: 'bg-blue-500/10 text-blue-400',
    CLOSED: 'bg-gray-700 text-gray-400',
    CANCELLED: 'bg-yellow-500/10 text-yellow-500',
  };
  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', styles[status])}>
      {status}
    </span>
  );
}

// Sort indicator
function SortIndicator({ isSorted }: { isSorted: false | 'asc' | 'desc' }) {
  if (!isSorted) return <span className="text-gray-700 ml-1" aria-hidden="true">⇅</span>;
  return (
    <span className="text-blue-400 ml-1" aria-hidden="true">
      {isSorted === 'asc' ? '↑' : '↓'}
    </span>
  );
}

// Skeleton loader row
function SkeletonRow({ columns }: { columns: number }) {
  return (
    <tr>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-gray-800 rounded animate-pulse w-3/4" />
        </td>
      ))}
    </tr>
  );
}

export default function TradeTable({ data, isLoading = false }: TradeTableProps) {
  const [sorting, setSorting] = React.useState<SortingState>([
    { id: 'entryDate', desc: true },
  ]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([]);
  const [pagination, setPagination] = React.useState<PaginationState>({
    pageIndex: 0,
    pageSize: 25,
  });

  const columns = useMemo(
    () => [
      columnHelper.accessor('symbol', {
        header: 'Symbol',
        cell: (info) => (
          <span className="font-mono font-semibold text-gray-100 text-sm">
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor('direction', {
        header: 'Direction',
        cell: (info) => <DirectionBadge direction={info.getValue()} />,
      }),
      columnHelper.accessor('status', {
        header: 'Status',
        cell: (info) => <StatusBadge status={info.getValue()} />,
      }),
      columnHelper.accessor('entryPrice', {
        header: 'Entry',
        cell: (info) => (
          <span className="tabular-nums text-sm text-gray-300">
            {formatCurrency(info.getValue())}
          </span>
        ),
      }),
      columnHelper.accessor('exitPrice', {
        header: 'Exit',
        cell: (info) => {
          const v = info.getValue();
          return (
            <span className="tabular-nums text-sm text-gray-300">
              {v !== null ? formatCurrency(v) : <span className="text-gray-600">—</span>}
            </span>
          );
        },
      }),
      columnHelper.accessor('quantity', {
        header: 'Qty',
        cell: (info) => (
          <span className="tabular-nums text-sm text-gray-300">
            {info.getValue().toLocaleString()}
          </span>
        ),
      }),
      columnHelper.accessor('pnl', {
        header: 'P&L',
        cell: (info) => {
          const v = info.getValue();
          if (v === null) return <span className="text-gray-600">—</span>;
          const positive = v >= 0;
          return (
            <span
              className={cn(
                'tabular-nums text-sm font-medium',
                positive ? 'text-green-400' : 'text-red-400'
              )}
            >
              {positive ? '+' : ''}{formatCurrency(v)}
            </span>
          );
        },
        sortDescFirst: true,
      }),
      columnHelper.accessor('pnlPct', {
        header: 'P&L %',
        cell: (info) => {
          const v = info.getValue();
          if (v === null) return <span className="text-gray-600">—</span>;
          const positive = v >= 0;
          return (
            <span
              className={cn(
                'tabular-nums text-sm',
                positive ? 'text-green-400' : 'text-red-400'
              )}
            >
              {positive ? '+' : ''}{formatPct(v)}
            </span>
          );
        },
      }),
      columnHelper.accessor('entryDate', {
        header: 'Entry Date',
        cell: (info) => (
          <span className="text-sm text-gray-400">
            {formatDate(info.getValue())}
          </span>
        ),
      }),
      columnHelper.accessor('strategy', {
        header: 'Strategy',
        cell: (info) => (
          <span className="text-sm text-gray-400">{info.getValue()}</span>
        ),
      }),
    ],
    []
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnFilters, pagination },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const isEmpty = !isLoading && data.length === 0;

  return (
    <div className="space-y-3">
    <div className="overflow-hidden rounded-lg border border-gray-800">
      <div className="overflow-x-auto">
        <table
          className="w-full text-left border-collapse"
          aria-label="Trade journal"
          aria-busy={isLoading}
        >
          <thead className="bg-gray-900 border-b border-gray-800">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className={cn(
                      'table-header',
                      header.column.getCanSort() &&
                        'cursor-pointer hover:text-gray-300 transition-colors'
                    )}
                    onClick={header.column.getToggleSortingHandler()}
                    aria-sort={
                      header.column.getIsSorted() === 'asc'
                        ? 'ascending'
                        : header.column.getIsSorted() === 'desc'
                        ? 'descending'
                        : 'none'
                    }
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {header.column.getCanSort() && (
                      <SortIndicator isSorted={header.column.getIsSorted()} />
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <SkeletonRow key={i} columns={columns.length} />
                ))
              : isEmpty
              ? (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="px-4 py-12 text-center text-sm text-gray-600"
                  >
                    No trades found
                  </td>
                </tr>
              )
              : table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className="hover:bg-gray-800/40 transition-colors duration-100"
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="table-cell">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </div>

    {/* Pagination controls */}
    {table.getPageCount() > 1 && (
      <div className="flex items-center justify-between px-1">
        <span className="text-xs text-gray-500 tabular-nums">
          Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
          {' · '}{table.getFilteredRowModel().rows.length} trades
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1.5 text-xs font-medium rounded bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            ← Prev
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1.5 text-xs font-medium rounded bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            Next →
          </button>
        </div>
      </div>
    )}
    </div>
  );
}
