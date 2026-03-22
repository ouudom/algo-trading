'use client';

import React, { useCallback, useRef, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadCsv, getDataFiles, deleteDataFile } from '@/lib/api';
import type { DataFileInfo } from '@/types';
import { cn } from '@/lib/utils';

interface CsvUploadCardProps {
  selectedFileId: string | null;
  onFileSelect: (_fileId: string) => void;
}

function formatDateRange(from: string, to: string): string {
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  return `${fmt(from)} — ${fmt(to)}`;
}

export default function CsvUploadCard({
  selectedFileId,
  onFileSelect,
}: CsvUploadCardProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const { data: files = [], isLoading: filesLoading, isError: filesError } = useQuery({
    queryKey: ['data-files'],
    queryFn: ({ signal }) => getDataFiles(signal),
  });

  const { mutate: upload, isPending: isUploading } = useMutation({
    mutationFn: ({ file, sym }: { file: File; sym: string }) =>
      uploadCsv(file, sym),
    onSuccess: (newFile) => {
      queryClient.invalidateQueries({ queryKey: ['data-files'] });
      onFileSelect(newFile.file_id);
      setUploadError(null);
    },
    onError: (err: Error) => {
      setUploadError(err.message || 'Upload failed');
    },
  });

  const { mutate: doDeleteFile, isPending: isDeletingFile } = useMutation({
    mutationFn: deleteDataFile,
    onSuccess: (_data, fileId) => {
      queryClient.invalidateQueries({ queryKey: ['data-files'] });
      setConfirmDeleteId(null);
      // Deselect if the deleted file was selected
      if (fileId === selectedFileId) onFileSelect('');
    },
  });

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList?.length) return;
      const file = fileList[0];
      if (!file.name.endsWith('.csv')) {
        setUploadError('Only .csv files are supported');
        return;
      }
      setUploadError(null);
      const sym = file.name.split('_')[0].toUpperCase();
      upload({ file, sym });
    },
    [upload]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 space-y-5">
      {/* Drop zone */}
      <div
        role="region"
        aria-label="CSV file drop zone"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          'flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-lg py-8 px-4 transition-colors duration-150',
          isDragOver
            ? 'border-blue-500 bg-blue-500/5'
            : 'border-gray-600 hover:border-gray-500'
        )}
      >
        {isUploading ? (
          <div className="flex flex-col items-center gap-2">
            <svg
              className="w-8 h-8 text-blue-400 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
              />
            </svg>
            <p className="text-sm text-gray-400">Uploading…</p>
          </div>
        ) : (
          <>
            <svg
              className="w-10 h-10 text-gray-600"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            <div className="text-center">
              <p className="text-sm text-gray-300">
                Drag &amp; drop a CSV (Dukascopy or HistData), or{' '}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-blue-400 hover:text-blue-300 underline underline-offset-2 focus:outline-none"
                >
                  browse
                </button>
              </p>
              <p className="text-xs text-gray-600 mt-1">
                .csv files only — OHLCV format
              </p>
            </div>
          </>
        )}
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        className="sr-only"
        aria-hidden="true"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {/* Upload error */}
      {uploadError && (
        <p
          className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-3 py-2"
          role="alert"
        >
          {uploadError}
        </p>
      )}

      {/* Uploaded files list */}
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
          Uploaded Files
        </p>

        {filesLoading ? (
          <div className="space-y-2">
            {[1, 2].map((n) => (
              <div
                key={n}
                className="h-14 bg-gray-700/40 rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : filesError ? (
          <p className="text-sm text-red-400 py-3 text-center">
            Could not load files — check that the backend is running.
          </p>
        ) : files.length === 0 ? (
          <p className="text-sm text-gray-600 py-3 text-center">
            No files uploaded yet
          </p>
        ) : (
          <ul className="space-y-1.5" role="listbox" aria-label="Uploaded CSV files">
            {files.map((f: DataFileInfo) => {
              const isSelected = f.file_id === selectedFileId;
              const isConfirming = confirmDeleteId === f.file_id;
              return (
                <li key={f.file_id} role="option" aria-selected={isSelected}>
                  <div
                    className={cn(
                      'rounded-lg border transition-colors duration-100',
                      isSelected
                        ? 'bg-blue-500/10 border-blue-500/40 ring-1 ring-blue-500/30'
                        : 'bg-gray-900/60 border-gray-700'
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => onFileSelect(f.file_id)}
                      className="w-full text-left px-4 pt-3 pb-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p
                            className={cn(
                              'text-sm font-medium truncate',
                              isSelected ? 'text-blue-300' : 'text-gray-200'
                            )}
                          >
                            {f.filename}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {f.symbol} · {f.timeframe} ·{' '}
                            {f.bars.toLocaleString()} bars ·{' '}
                            {formatDateRange(f.date_from, f.date_to)}
                          </p>
                        </div>
                        {isSelected && (
                          <svg
                            className="w-4 h-4 text-blue-400 shrink-0 mt-0.5"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={2.5}
                            viewBox="0 0 24 24"
                            aria-label="Selected"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M4.5 12.75l6 6 9-13.5"
                            />
                          </svg>
                        )}
                      </div>
                    </button>

                    {/* Delete row */}
                    <div className="px-4 pb-2.5 flex items-center justify-end gap-2">
                      {isConfirming ? (
                        <>
                          <span className="text-xs text-gray-400">Delete file?</span>
                          <button
                            type="button"
                            onClick={() => doDeleteFile(f.file_id)}
                            disabled={isDeletingFile}
                            className="text-xs px-2 py-0.5 rounded bg-red-600 hover:bg-red-500 text-white font-medium transition-colors"
                          >
                            {isDeletingFile ? '…' : 'Yes'}
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteId(null)}
                            className="text-xs px-2 py-0.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
                          >
                            No
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(f.file_id)}
                          className="text-gray-600 hover:text-red-400 transition-colors"
                          aria-label="Delete file"
                          title="Delete file"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
