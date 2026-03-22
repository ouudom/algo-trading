'use client';

import React, { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { runBacktest } from '@/lib/api';
import type { DataFileInfo, BacktestRunRequest } from '@/types';
import { cn } from '@/lib/utils';

// ─── Types ────────────────────────────────────────────────────────────────────

interface BacktestConfigFormProps {
  selectedFileId: string | null;
  selectedFile: DataFileInfo | null;
  onRunStarted: (_runId: string) => void;
  /** Disable the form while a backtest is running */
  disabled?: boolean;
}

type StrategyType = 'ma_crossover' | 'rsi_momentum';

interface FormState {
  symbol: string;
  timeframe: string;
  strategy: StrategyType;
  // MA Crossover params
  ema_fast: number;
  ema_slow: number;
  use_sma200_filter: boolean;
  // RSI Momentum params
  rsi_period: number;
  rsi_threshold: number;
  trend_ema_period: number;
  // Shared params
  atr_period: number;
  sl_multiplier: number;
  tp_multiplier: number;
  initial_equity: number;
  start_date: string;
  end_date: string;
  be_enabled: boolean;
  be_trigger_pct_display: number; // integer % shown in UI (e.g. 50 → 0.50 sent to API)
}

const TIMEFRAMES = [
  { value: 'M1',  label: 'M1  — 1 Minute' },
  { value: 'M5',  label: 'M5  — 5 Minutes' },
  { value: 'M15', label: 'M15 — 15 Minutes' },
  { value: 'M30', label: 'M30 — 30 Minutes' },
  { value: 'H1',  label: 'H1  — 1 Hour' },
  { value: 'H4',  label: 'H4  — 4 Hours' },
  { value: 'D1',  label: 'D1  — Daily' },
] as const;

const STRATEGIES: { value: StrategyType; label: string }[] = [
  { value: 'ma_crossover', label: 'MA Crossover' },
  { value: 'rsi_momentum', label: 'RSI Momentum' },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toDateInput(isoString: string): string {
  if (!isoString) return '';
  return isoString.slice(0, 10);
}

// ─── Field wrapper ────────────────────────────────────────────────────────────

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-semibold uppercase tracking-wider text-gray-500">
        {label}
      </label>
      {children}
    </div>
  );
}

const inputCls =
  'bg-gray-900 border border-gray-700 rounded-md px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500 tabular-nums w-full';

// ─── Component ────────────────────────────────────────────────────────────────

export default function BacktestConfigForm({
  selectedFileId,
  selectedFile,
  onRunStarted,
  disabled = false,
}: BacktestConfigFormProps) {
  const [form, setForm] = useState<FormState>({
    symbol: 'XAUUSD',
    timeframe: 'H1',
    strategy: 'ma_crossover',
    // MA Crossover defaults
    ema_fast: 20, ema_slow: 50, use_sma200_filter: false,
    // RSI Momentum defaults
    rsi_period: 14, rsi_threshold: 50, trend_ema_period: 200,
    // Shared defaults
    atr_period: 14, sl_multiplier: 1.5, tp_multiplier: 3.0,
    initial_equity: 10000,
    start_date: '',
    end_date: '',
    be_enabled: false,
    be_trigger_pct_display: 50,
  });
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Pre-fill dates and symbol when a file is selected; always parse symbol from filename
  useEffect(() => {
    if (selectedFile) {
      const sym = selectedFile.filename.split('_')[0].toUpperCase();
      setForm((prev) => ({
        ...prev,
        symbol: sym || selectedFile.symbol || prev.symbol,
        start_date: toDateInput(selectedFile.date_from),
        end_date: toDateInput(selectedFile.date_to),
      }));
    }
  }, [selectedFile]);

  const { mutate: submit, isPending } = useMutation({
    mutationFn: (req: BacktestRunRequest) => runBacktest(req),
    onSuccess: (res) => {
      setSubmitError(null);
      onRunStarted(res.run_id);
    },
    onError: (err: Error) => {
      setSubmitError(err.message || 'Failed to submit backtest');
    },
  });

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFileId) return;

    const sharedFields = {
      file_id: selectedFileId,
      symbol: form.symbol,
      variation: 'V1',
      strategy: form.strategy,
      timeframe: form.timeframe,
      atr_period: form.atr_period,
      sl_multiplier: form.sl_multiplier,
      tp_multiplier: form.tp_multiplier,
      initial_equity: form.initial_equity,
      be_trigger_pct: form.be_enabled ? form.be_trigger_pct_display / 100 : 0,
      ...(form.start_date ? { start_date: form.start_date } : {}),
      ...(form.end_date ? { end_date: form.end_date } : {}),
    };

    const req: BacktestRunRequest =
      form.strategy === 'rsi_momentum'
        ? {
            ...sharedFields,
            // Required by type; API ignores them for rsi_momentum path
            ema_fast: 20,
            ema_slow: 50,
            rsi_period: form.rsi_period,
            rsi_threshold: form.rsi_threshold,
            trend_ema_period: form.trend_ema_period,
          }
        : {
            ...sharedFields,
            ema_fast: form.ema_fast,
            ema_slow: form.ema_slow,
            use_sma200_filter: form.use_sma200_filter,
          };

    submit(req);
  }

  const canSubmit = !!selectedFileId && !isPending && !disabled;

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-5">

          {/* Strategy selector */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
              Strategy
            </p>
            <div className="flex gap-2">
              {STRATEGIES.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setField('strategy', value)}
                  className={cn(
                    'px-4 py-1.5 rounded-full text-xs font-semibold transition-colors duration-150',
                    form.strategy === value
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Timeframe row */}
          <div className="grid grid-cols-2 gap-x-6">
            <Field label="Timeframe">
              <select
                value={form.timeframe}
                onChange={(e) => setField('timeframe', e.target.value)}
                className={inputCls}
                aria-label="Backtest timeframe"
              >
                {TIMEFRAMES.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </Field>
          </div>

          {/* MA Crossover params */}
          {form.strategy === 'ma_crossover' && (
            <>
              <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
                <Field label="EMA Fast">
                  <input
                    type="number"
                    min={1}
                    value={form.ema_fast}
                    onChange={(e) => setField('ema_fast', Number(e.target.value))}
                    className={inputCls}
                    aria-label="EMA Fast period"
                  />
                </Field>
                <Field label="EMA Slow">
                  <input
                    type="number"
                    min={1}
                    value={form.ema_slow}
                    onChange={(e) => setField('ema_slow', Number(e.target.value))}
                    className={inputCls}
                    aria-label="EMA Slow period"
                  />
                </Field>
                <Field label="ATR Period">
                  <input
                    type="number"
                    min={1}
                    value={form.atr_period}
                    onChange={(e) => setField('atr_period', Number(e.target.value))}
                    className={inputCls}
                    aria-label="ATR Period"
                  />
                </Field>
                <Field label="SL Multiplier (ATR×)">
                  <input
                    type="number"
                    min={0.1}
                    step={0.1}
                    value={form.sl_multiplier}
                    onChange={(e) => setField('sl_multiplier', Number(e.target.value))}
                    className={inputCls}
                    aria-label="Stop-loss ATR multiplier"
                  />
                </Field>
                <Field label="TP Multiplier (ATR×)">
                  <input
                    type="number"
                    min={0.1}
                    step={0.1}
                    value={form.tp_multiplier}
                    onChange={(e) => setField('tp_multiplier', Number(e.target.value))}
                    className={inputCls}
                    aria-label="Take-profit ATR multiplier"
                  />
                </Field>
                <Field label="Initial Equity ($)">
                  <input
                    type="number"
                    min={100}
                    step={100}
                    value={form.initial_equity}
                    onChange={(e) => setField('initial_equity', Number(e.target.value))}
                    className={inputCls}
                    aria-label="Initial equity in dollars"
                  />
                </Field>
              </div>

              {/* SMA(200) Trend Filter */}
              <div className="border border-gray-700 rounded-lg p-4">
                <label className="flex items-center gap-2.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={form.use_sma200_filter}
                    onChange={(e) => setField('use_sma200_filter', e.target.checked)}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-900 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                    aria-label="Enable SMA 200 trend filter"
                  />
                  <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                    SMA(200) Trend Filter
                  </span>
                  <span className="ml-auto text-xs font-medium">
                    {form.use_sma200_filter ? (
                      <span className="text-blue-400">ON — trades with trend only</span>
                    ) : (
                      <span className="text-gray-500">OFF — all crossovers taken</span>
                    )}
                  </span>
                </label>
              </div>
            </>
          )}

          {/* RSI Momentum params */}
          {form.strategy === 'rsi_momentum' && (
            <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
              <Field label="RSI Period">
                <input
                  type="number"
                  min={2}
                  value={form.rsi_period}
                  onChange={(e) => setField('rsi_period', Number(e.target.value))}
                  className={inputCls}
                  aria-label="RSI period"
                />
              </Field>
              <Field label="RSI Threshold">
                <input
                  type="number"
                  min={1}
                  max={99}
                  step={1}
                  value={form.rsi_threshold}
                  onChange={(e) => setField('rsi_threshold', Number(e.target.value))}
                  className={inputCls}
                  aria-label="RSI threshold level"
                />
              </Field>
              <Field label="Trend EMA Period">
                <input
                  type="number"
                  min={2}
                  value={form.trend_ema_period}
                  onChange={(e) => setField('trend_ema_period', Number(e.target.value))}
                  className={inputCls}
                  aria-label="Trend EMA period"
                />
              </Field>
              <Field label="ATR Period">
                <input
                  type="number"
                  min={1}
                  value={form.atr_period}
                  onChange={(e) => setField('atr_period', Number(e.target.value))}
                  className={inputCls}
                  aria-label="ATR Period"
                />
              </Field>
              <Field label="SL Multiplier (ATR×)">
                <input
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={form.sl_multiplier}
                  onChange={(e) => setField('sl_multiplier', Number(e.target.value))}
                  className={inputCls}
                  aria-label="Stop-loss ATR multiplier"
                />
              </Field>
              <Field label="TP Multiplier (ATR×)">
                <input
                  type="number"
                  min={0.1}
                  step={0.1}
                  value={form.tp_multiplier}
                  onChange={(e) => setField('tp_multiplier', Number(e.target.value))}
                  className={inputCls}
                  aria-label="Take-profit ATR multiplier"
                />
              </Field>
              <Field label="Initial Equity ($)">
                <input
                  type="number"
                  min={100}
                  step={100}
                  value={form.initial_equity}
                  onChange={(e) => setField('initial_equity', Number(e.target.value))}
                  className={inputCls}
                  aria-label="Initial equity in dollars"
                />
              </Field>
            </div>
          )}

          {/* RR summary hint */}
          <p className="text-xs text-gray-600">
            SL = ATR × {form.sl_multiplier} &nbsp;·&nbsp;
            TP = ATR × {form.tp_multiplier} &nbsp;·&nbsp;
            RR 1 : {form.sl_multiplier > 0 ? (form.tp_multiplier / form.sl_multiplier).toFixed(2) : '—'}
          </p>

          {/* Break Even */}
          <div className="border border-gray-700 rounded-lg p-4 space-y-3">
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.be_enabled}
                onChange={(e) => setField('be_enabled', e.target.checked)}
                className="w-4 h-4 rounded border-gray-600 bg-gray-900 text-amber-500 focus:ring-amber-500 focus:ring-offset-0"
                aria-label="Enable break even"
              />
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                Break Even
              </span>
              {form.be_enabled && (
                <span className="ml-auto text-xs text-amber-400 font-medium">
                  SL → entry at {form.be_trigger_pct_display}% of TP
                </span>
              )}
            </label>
            {form.be_enabled && (
              <div className="flex items-center gap-3">
                <Field label="BE Trigger (% of TP)">
                  <input
                    type="number"
                    min={1}
                    max={99}
                    step={1}
                    value={form.be_trigger_pct_display}
                    onChange={(e) =>
                      setField('be_trigger_pct_display', Math.min(99, Math.max(1, Number(e.target.value))))
                    }
                    className={inputCls}
                    aria-label="Break even trigger percentage of TP distance"
                  />
                </Field>
                <p className="text-xs text-gray-600 mt-5 leading-snug">
                  Moves SL to entry once price travels {form.be_trigger_pct_display}% toward TP
                </p>
              </div>
            )}
          </div>

          {/* Date range */}
          <div className="grid grid-cols-2 gap-x-6">
            <Field label="Start Date">
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => setField('start_date', e.target.value)}
                className={cn(inputCls, 'cursor-pointer')}
                aria-label="Backtest start date"
              />
            </Field>
            <Field label="End Date">
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => setField('end_date', e.target.value)}
                className={cn(inputCls, 'cursor-pointer')}
                aria-label="Backtest end date"
              />
            </Field>
          </div>

          {/* File required hint */}
          {!selectedFileId && (
            <p className="text-xs text-yellow-500 bg-yellow-500/10 border border-yellow-500/20 rounded px-3 py-2">
              Select a data file above before running the backtest.
            </p>
          )}

          {/* Submit error */}
          {submitError && (
            <p
              className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-3 py-2"
              role="alert"
            >
              {submitError}
            </p>
          )}

          {/* Submit button */}
          <div className="pt-1">
            <button
              type="submit"
              disabled={!canSubmit}
              className={cn(
                'inline-flex items-center gap-2 px-5 py-2.5 rounded-md text-sm font-semibold transition-colors duration-150',
                canSubmit
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : 'bg-gray-700 text-gray-500 cursor-not-allowed'
              )}
              aria-busy={isPending}
            >
              {isPending ? (
                <>
                  <svg
                    className="w-4 h-4 animate-spin"
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
                  Submitting…
                </>
              ) : (
                <>
                  <span aria-hidden="true">&#9654;</span>
                  Run Backtest
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
