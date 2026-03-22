'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getDataFiles, getBacktestStatus } from '@/lib/api';
import CsvUploadCard from './CsvUploadCard';
import BacktestConfigForm from './BacktestConfigForm';
import BacktestResultPanel from './BacktestResultPanel';
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
        {progress > 0 && (
          <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
        )}
      </div>
      <span className="text-xs text-blue-400 tabular-nums shrink-0">
        {progress > 0 ? `${Math.round(progress)}%` : 'Waiting…'}
      </span>
    </div>
  );
}

// ─── Modal ────────────────────────────────────────────────────────────────────

interface RunTestModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function RunTestModal({ open, onClose, onSuccess }: RunTestModalProps) {
  const queryClient = useQueryClient();

  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const { data: files = [] } = useQuery({
    queryKey: ['data-files'],
    queryFn: getDataFiles,
    enabled: open,
  });

  const selectedFile: DataFileInfo | null =
    files.find((f: DataFileInfo) => f.file_id === selectedFileId) ?? null;

  const { data: runStatus } = useQuery({
    queryKey: ['backtest-status', activeRunId],
    queryFn: () => getBacktestStatus(activeRunId!),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === 'completed' || s === 'failed' ? false : 3000;
    },
    enabled: !!activeRunId,
  });

  // Notify parent when a run completes
  const prevStatus = runStatus?.status;
  useEffect(() => {
    if (prevStatus === 'completed') {
      onSuccess();
      queryClient.invalidateQueries({ queryKey: ['backtests'] });
    }
  }, [prevStatus, onSuccess, queryClient]);

  // Reset state when modal closes
  useEffect(() => {
    if (!open) {
      setSelectedFileId(null);
      setActiveRunId(null);
    }
  }, [open]);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  const handleFileSelect = useCallback((fileId: string) => setSelectedFileId(fileId), []);
  const handleRunStarted = useCallback((runId: string) => setActiveRunId(runId), []);

  const isRunning =
    !!activeRunId &&
    !!runStatus &&
    runStatus.status !== 'completed' &&
    runStatus.status !== 'failed';

  const isCompleted = !!activeRunId && runStatus?.status === 'completed';
  const isFailed = !!activeRunId && runStatus?.status === 'failed';

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal card */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className={cn(
          'relative z-10 w-full max-w-4xl mx-4 my-8',
          'bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl',
          'max-h-[90vh] overflow-y-auto',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-700 sticky top-0 bg-gray-900 z-10">
          <div>
            <h2 id="modal-title" className="text-lg font-semibold text-white">Run Backtest</h2>
            <p className="text-sm text-gray-500 mt-0.5">Upload price data and configure a strategy variant.</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-gray-500 hover:text-gray-300 transition-colors p-1 rounded"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-6 space-y-6">
          {/* 1. Upload */}
          <section>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">1. Upload Data</h3>
            <CsvUploadCard selectedFileId={selectedFileId} onFileSelect={handleFileSelect} />
          </section>

          {/* 2. Configure */}
          <section>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">2. Configure &amp; Run</h3>
            <BacktestConfigForm
              selectedFileId={selectedFileId}
              selectedFile={selectedFile}
              onRunStarted={handleRunStarted}
            />
          </section>

          {/* Status banner */}
          {isRunning && <StatusBanner status={runStatus.status} progress={runStatus.progress_pct} />}

          {/* Failed banner */}
          {isFailed && (
            <div
              role="alert"
              className="flex items-center gap-3 bg-red-500/10 border border-red-500/20 rounded-xl px-5 py-4"
            >
              <svg
                className="w-5 h-5 text-red-400 shrink-0"
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
                {runStatus?.error && (
                  <p className="text-xs text-red-400/80 mt-0.5">{runStatus.error}</p>
                )}
              </div>
            </div>
          )}

          {/* Results */}
          {isCompleted && (
            <section>
              <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">3. Results</h3>
              <BacktestResultPanel runId={activeRunId!} />
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
