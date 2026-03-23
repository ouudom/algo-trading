'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getDataFiles, getBacktestStatus } from '@/lib/api';
import CsvUploadCard from '@/components/backtests/CsvUploadCard';
import BacktestConfigForm from '@/components/backtests/BacktestConfigForm';
import { cn } from '@/lib/utils';
import type { DataFileInfo } from '@/types';

// ─── Status banner ────────────────────────────────────────────────────────────

function StatusBanner({ status, progress }: { status: string; progress: number }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-4 bg-blue-500/10 border border-blue-500/20 rounded-xl px-5 py-4"
    >
      <svg
        className="w-5 h-5 text-blue-400 animate-spin shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
      </svg>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-blue-300">
          Backtest {status === 'pending' ? 'queued' : 'running'}…
        </p>
        <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(Math.max(progress, 5), 100)}%` }}
          />
        </div>
      </div>
      <span className="text-xs text-blue-400 tabular-nums shrink-0">
        {progress > 0 ? `${Math.round(progress)}%` : 'Waiting…'}
      </span>
    </div>
  );
}

function FailedBanner({ error }: { error?: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-xl px-5 py-4"
    >
      <svg
        className="w-5 h-5 text-red-400 shrink-0 mt-0.5"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <div>
        <p className="text-sm font-medium text-red-300">Backtest failed</p>
        {error && <p className="text-xs text-red-400/80 mt-0.5">{error}</p>}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function NewBacktestPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId]       = useState<string | null>(null);

  const { data: files = [] } = useQuery({
    queryKey: ['data-files'],
    queryFn: ({ signal }) => getDataFiles(signal),
  });

  const selectedFile: DataFileInfo | null =
    files.find((f: DataFileInfo) => f.file_id === selectedFileId) ?? null;

  const { data: runStatus } = useQuery({
    queryKey: ['backtest-status', activeRunId],
    queryFn:  () => getBacktestStatus(activeRunId!),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === 'completed' || s === 'failed' ? false : 2000;
    },
    enabled: !!activeRunId,
  });

  // Redirect to detail page when run completes
  useEffect(() => {
    if (runStatus?.status === 'completed' && activeRunId) {
      queryClient.invalidateQueries({ queryKey: ['backtests'] });
      router.push(`/backtests/${activeRunId}`);
    }
  }, [runStatus?.status, activeRunId, router, queryClient]);

  const handleFileSelect = useCallback((fileId: string) => setSelectedFileId(fileId || null), []);
  const handleRunStarted = useCallback((runId: string) => setActiveRunId(runId), []);

  const isRunning =
    !!activeRunId &&
    !!runStatus &&
    runStatus.status !== 'completed' &&
    runStatus.status !== 'failed';

  const isFailed = !!activeRunId && runStatus?.status === 'failed';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          href="/backtests"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-300 transition-colors mb-4"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Backtests
        </Link>
        <h1 className="text-2xl font-bold text-white">New Backtest</h1>
        <p className="text-sm text-gray-500 mt-1">Upload price data and configure your strategy parameters.</p>
      </div>

      {/* Two-column layout */}
      <div className={cn('grid gap-6', 'lg:grid-cols-[1fr_1fr]')}>
        {/* Left — data upload */}
        <div className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            1. Select Data
          </h2>
          <CsvUploadCard selectedFileId={selectedFileId} onFileSelect={handleFileSelect} />
        </div>

        {/* Right — configuration */}
        <div className="space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            2. Configure &amp; Run
          </h2>
          <BacktestConfigForm
            selectedFileId={selectedFileId}
            selectedFile={selectedFile}
            onRunStarted={handleRunStarted}
            disabled={isRunning}
          />

          {/* Status / error */}
          {isRunning && (
            <StatusBanner status={runStatus.status} progress={runStatus.progress_pct} />
          )}
          {isFailed && (
            <FailedBanner error={runStatus?.error} />
          )}
        </div>
      </div>
    </div>
  );
}
