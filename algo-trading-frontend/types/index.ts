// ─── Trade ────────────────────────────────────────────────────────────────────

export type TradeDirection = 'LONG' | 'SHORT';
export type TradeStatus = 'OPEN' | 'CLOSED' | 'CANCELLED';

export interface Trade {
  id: string;
  symbol: string;
  direction: TradeDirection;
  status: TradeStatus;
  entryPrice: number;
  exitPrice: number | null;
  quantity: number;
  pnl: number | null;
  pnlPct: number | null;
  entryDate: string;
  exitDate: string | null;
  strategy: string;
  notes: string | null;
}

// ─── Backtest ─────────────────────────────────────────────────────────────────

export interface BacktestRun {
  id: string;
  symbol: string;
  timeframe: string;
  variation: string;
  start_date: string | null;
  end_date: string | null;
  initial_equity: number;
  final_equity: number | null;
  total_trades: number;
  win_rate: number | null;
  profit_factor: number | null;
  total_return_pct: number | null;
  sharpe_ratio: number | null;
  max_drawdown_pct: number | null;
  params_json?: Record<string, unknown>;
  status: string;
  created_at: string;
}

// ─── Backtest Trade ───────────────────────────────────────────────────────────

export interface BacktestTrade {
  id: string;
  symbol: string;
  direction: number; // 1 = LONG, -1 = SHORT
  lots: number;
  entry_price: number;
  sl_price: number;
  tp_price: number;
  entry_time: string;
  exit_price: number;
  exit_time: string;
  exit_reason: 'SL' | 'TP' | 'BE' | 'EOD' | string;
  pnl: number;
  variation: string;
}

// ─── Data Files ───────────────────────────────────────────────────────────────

export interface DataFileInfo {
  file_id: string;
  filename: string;
  symbol: string;
  timeframe: string;
  bars: number;
  date_from: string;
  date_to: string;
  uploaded_at: string;
}

// ─── Backtest run request / response ─────────────────────────────────────────

export interface BacktestRunRequest {
  file_id: string;
  symbol: string;
  variation: string;
  strategy?: 'ma_crossover' | 'rsi_momentum';
  timeframe?: string;
  // MA Crossover params
  ema_fast: number;
  ema_slow: number;
  use_sma200_filter?: boolean; // true = only trade with SMA(200) trend direction
  sma200_period?: number;      // look-back window for the SMA trend filter (default 200)
  // RSI Momentum params
  rsi_period?: number;
  rsi_threshold?: number;
  trend_ema_period?: number;
  // Shared params
  atr_period: number;
  sl_multiplier: number;
  tp_multiplier: number;
  be_trigger_pct?: number; // 0 = disabled; e.g. 0.5 = move SL to entry at 50% of TP distance
  start_date?: string;
  end_date?: string;
  initial_equity: number;
}

export interface BacktestSubmitResponse {
  run_id: string;
  status: string;
}

export interface BacktestStatusResponse {
  run_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress_pct: number;
  error?: string;
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export interface AnalyticsMetrics {
  totalReturn: number;
  totalReturnPct: number;
  sharpeRatio: number;
  sortinoRatio: number;
  maxDrawdown: number;
  maxDrawdownPct: number;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  avgWin: number;
  avgLoss: number;
  avgHoldingDays: number;
  bestTrade: number;
  worstTrade: number;
}

// ─── Chart data ───────────────────────────────────────────────────────────────

export interface EquityDataPoint {
  date: string;
  equity: number;
}

export interface DrawdownDataPoint {
  date: string;
  drawdown: number;
}

// ─── API response wrappers ────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  detail: string;
  status: number;
}

// ─── Dashboard summary ────────────────────────────────────────────────────────

export interface DashboardSummary {
  accountEquity: number;
  dailyPnl: number;
  dailyPnlPct: number;
  openPositions: number;
  totalTrades: number;
  winRate: number;
  equityCurve: EquityDataPoint[];
}

// ─── Mode ─────────────────────────────────────────────────────────────────────

export type TradingMode = 'LIVE' | 'PAPER';

// ─── Live Trade ───────────────────────────────────────────────────────────────

export type LiveTradeStatus = 'open' | 'closed' | 'error';

export interface LiveTrade {
  id: string;
  symbol: string;
  direction: number;       // 1 = LONG, -1 = SHORT
  lots: number;
  entry_price: number;
  sl_price: number;
  tp_price: number;
  entry_time: string;
  exit_price: number | null;
  exit_time: string | null;
  exit_reason: 'SL' | 'TP' | 'manual' | 'circuit_break' | string | null;
  pnl: number | null;
  status: LiveTradeStatus;
  strategy: string;
  variation: string;
  ticket: number;
  account_equity_at_entry: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface LiveStats {
  total_trades: number;
  open_count: number;
  closed_count: number;
  win_count: number;
  loss_count: number;
  total_pnl: number;
  today_pnl: number;
}

// ─── Live Trading Config ──────────────────────────────────────────────────────

export type LiveConfigStatus =
  | 'idle'
  | 'running'
  | 'halted_daily'
  | 'halted_drawdown'
  | 'error';

export interface LiveTradingConfig {
  id: string;
  symbol: string;
  variation: string;
  strategy: string;
  enabled: boolean;
  status: LiveConfigStatus;
  last_run_at: string | null;
  last_signal: number | null;
  last_error: string | null;
  peak_equity: number | null;
  session_start_equity: number | null;
  created_at: string;
  updated_at: string;
}
