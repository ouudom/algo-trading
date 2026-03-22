import type {
  Trade,
  BacktestRun,
  BacktestTrade,
  AnalyticsMetrics,
  DashboardSummary,
  PaginatedResponse,
  EquityDataPoint,
  DrawdownDataPoint,
  DataFileInfo,
  BacktestRunRequest,
  BacktestSubmitResponse,
  BacktestStatusResponse,
  LiveTrade,
  LiveTradingConfig,
  LiveStats,
} from '@/types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const API_V1 = `${BASE_URL}/api/v1`;

// ─── Generic fetch helper ─────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  base = API_V1
): Promise<T> {
  const url = `${base}${path}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(
      `API error ${res.status} ${res.statusText}: ${body}`
    );
  }

  return res.json() as Promise<T>;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>('/dashboard/summary');
}

export async function getEquityCurve(): Promise<EquityDataPoint[]> {
  return apiFetch<EquityDataPoint[]>('/dashboard/equity-curve');
}

// ─── Trades ───────────────────────────────────────────────────────────────────

export interface GetTradesParams {
  page?: number;
  pageSize?: number;
  symbol?: string;
  direction?: 'LONG' | 'SHORT';
  status?: 'OPEN' | 'CLOSED' | 'CANCELLED';
  sortBy?: keyof Trade;
  sortOrder?: 'asc' | 'desc';
}

export async function getTrades(
  params: GetTradesParams = {}
): Promise<PaginatedResponse<Trade>> {
  const query = new URLSearchParams();
  if (params.page !== undefined) query.set('page', String(params.page));
  if (params.pageSize !== undefined) query.set('page_size', String(params.pageSize));
  if (params.symbol) query.set('symbol', params.symbol);
  if (params.direction) query.set('direction', params.direction);
  if (params.status) query.set('status', params.status);
  if (params.sortBy) query.set('sort_by', params.sortBy as string);
  if (params.sortOrder) query.set('sort_order', params.sortOrder);

  const qs = query.toString();
  return apiFetch<PaginatedResponse<Trade>>(`/trades${qs ? `?${qs}` : ''}`);
}

export async function getTradeById(id: string): Promise<Trade> {
  return apiFetch<Trade>(`/trades/${id}`);
}

// ─── Backtests ────────────────────────────────────────────────────────────────

export interface GetBacktestsParams {
  limit?: number;
  offset?: number;
  symbol?: string;
  variation?: string;
}

export async function getBacktests(
  params: GetBacktestsParams = {}
): Promise<BacktestRun[]> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  if (params.symbol) query.set('symbol', params.symbol);
  if (params.variation) query.set('variation', params.variation);

  const qs = query.toString();
  return apiFetch<BacktestRun[]>(`/backtests${qs ? `?${qs}` : ''}`);
}

export async function getBacktestById(id: string): Promise<BacktestRun> {
  return apiFetch<BacktestRun>(`/backtests/${id}`);
}

export async function getBacktestTrades(id: string): Promise<BacktestTrade[]> {
  return apiFetch<BacktestTrade[]>(`/backtests/${id}/trades`);
}

export async function getBacktestDrawdown(id: string): Promise<DrawdownDataPoint[]> {
  return apiFetch<DrawdownDataPoint[]>(`/backtests/${id}/drawdown`);
}

interface BacktestEquityCurveResponse {
  run_id: string;
  initial_equity: number;
  points: { timestamp: string; equity: number }[];
}

export async function getBacktestEquity(id: string): Promise<BacktestEquityCurveResponse> {
  return apiFetch<BacktestEquityCurveResponse>(`/backtests/${id}/equity`);
}

export interface CandleBar {
  time:     number;   // Unix seconds UTC
  open:     number;
  high:     number;
  low:      number;
  close:    number;
  ema_fast: number | null;
  ema_slow: number | null;
}

export async function getBacktestCandles(id: string): Promise<CandleBar[]> {
  return apiFetch<CandleBar[]>(`/backtests/${id}/candles`);
}

// ─── Data files ───────────────────────────────────────────────────────────────

export async function uploadCsv(file: File, symbol: string): Promise<DataFileInfo> {
  const formData = new FormData();
  formData.append('file', file);
  // Timeframe is auto-detected server-side from bar intervals; no need to send it
  const url = `${API_V1}/data/upload?symbol=${encodeURIComponent(symbol)}`;
  const res = await fetch(url, { method: 'POST', body: formData });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<DataFileInfo>;
}

export async function getDataFiles(signal?: AbortSignal): Promise<DataFileInfo[]> {
  const timeout = AbortSignal.timeout(10_000);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  return apiFetch<DataFileInfo[]>('/data/files', { signal: combined });
}

export async function deleteDataFile(fileId: string): Promise<void> {
  const url = `${API_V1}/data/files/${encodeURIComponent(fileId)}`;
  const res = await fetch(url, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}

// ─── Async backtest run ───────────────────────────────────────────────────────

export async function runBacktest(req: BacktestRunRequest): Promise<BacktestSubmitResponse> {
  return apiFetch<BacktestSubmitResponse>('/backtests/run', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function getBacktestStatus(runId: string): Promise<BacktestStatusResponse> {
  return apiFetch<BacktestStatusResponse>(`/backtests/${runId}/status`);
}

export async function deleteBacktest(runId: string): Promise<void> {
  const url = `${API_V1}/backtests/${encodeURIComponent(runId)}`;
  const res = await fetch(url, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export interface GetAnalyticsParams {
  startDate?: string;
  endDate?: string;
  symbol?: string;
  strategy?: string;
}

export async function getAnalytics(
  params: GetAnalyticsParams = {}
): Promise<AnalyticsMetrics> {
  const query = new URLSearchParams();
  if (params.startDate) query.set('start_date', params.startDate);
  if (params.endDate) query.set('end_date', params.endDate);
  if (params.symbol) query.set('symbol', params.symbol);
  if (params.strategy) query.set('strategy', params.strategy);

  const qs = query.toString();
  return apiFetch<AnalyticsMetrics>(`/analytics${qs ? `?${qs}` : ''}`);
}

// ─── Live Trading ─────────────────────────────────────────────────────────────

export async function getLiveConfigs(): Promise<LiveTradingConfig[]> {
  return apiFetch<LiveTradingConfig[]>('/live-trades/configs');
}

export async function createLiveConfig(
  symbol: string,
  variation: string,
  strategy = 'MA_ATR'
): Promise<LiveTradingConfig> {
  return apiFetch<LiveTradingConfig>('/live-trades/configs', {
    method: 'POST',
    body: JSON.stringify({ symbol, variation, strategy }),
  });
}

export async function updateLiveConfig(
  id: string,
  body: { variation?: string; strategy?: string }
): Promise<LiveTradingConfig> {
  return apiFetch<LiveTradingConfig>(`/live-trades/configs/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export async function deleteLiveConfig(id: string): Promise<void> {
  const url = `${API_V1}/live-trades/configs/${encodeURIComponent(id)}`;
  const res = await fetch(url, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
}

export async function enableLiveConfig(id: string): Promise<LiveTradingConfig> {
  return apiFetch<LiveTradingConfig>(`/live-trades/configs/${id}/enable`, {
    method: 'POST',
  });
}

export async function disableLiveConfig(id: string): Promise<LiveTradingConfig> {
  return apiFetch<LiveTradingConfig>(`/live-trades/configs/${id}/disable`, {
    method: 'POST',
  });
}

export async function getLiveTrades(params: {
  symbol?: string;
  status?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<LiveTrade[]> {
  const query = new URLSearchParams();
  if (params.symbol) query.set('symbol', params.symbol);
  if (params.status) query.set('status', params.status);
  if (params.limit !== undefined) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  const qs = query.toString();
  return apiFetch<LiveTrade[]>(`/live-trades${qs ? `?${qs}` : ''}`);
}

export async function getOpenLivePositions(symbol?: string): Promise<LiveTrade[]> {
  const qs = symbol ? `?symbol=${encodeURIComponent(symbol)}` : '';
  return apiFetch<LiveTrade[]>(`/live-trades/open${qs}`);
}

export async function getLiveStats(): Promise<LiveStats> {
  return apiFetch<LiveStats>('/live-trades/stats');
}

export async function getAnalyticsDrawdown(
  params: GetAnalyticsParams = {}
): Promise<DrawdownDataPoint[]> {
  const query = new URLSearchParams();
  if (params.startDate) query.set('start_date', params.startDate);
  if (params.endDate) query.set('end_date', params.endDate);
  if (params.symbol) query.set('symbol', params.symbol);
  if (params.strategy) query.set('strategy', params.strategy);

  const qs = query.toString();
  return apiFetch<DrawdownDataPoint[]>(`/analytics/drawdown${qs ? `?${qs}` : ''}`);
}
