"""
backtest.py - Vectorised event-driven backtesting engine.

The engine replays historical OHLCV bars, processes signals from
:func:`algo_trading.signal.generate_signals`, and simulates trade execution
with realistic stop-loss and take-profit logic.

Design decisions
----------------
* Bar-close execution: entries and exits fire at the **next bar's open** after
  a signal fires (to avoid look-ahead bias).
* SL/TP are checked against the *high* and *low* of the execution bar.
* One position at a time — new signals are ignored while a trade is open.
* No slippage model by default; a fixed ``commission_per_lot`` is deducted.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from algo_trading.signal import generate_rsi_signals, generate_signals
from algo_trading.signal.signal import RsiSignalParams, SignalParams

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class BacktestParams:
    """Configuration for a single backtest run.

    Attributes
    ----------
    signal_params:
        Strategy hyper-parameters forwarded to :func:`generate_signals`.
    initial_equity:
        Starting account equity in account currency. Default 10 000.
    risk_pct:
        Fraction of equity risked per trade. Default 0.01 (1 %).
    pip_value:
        Monetary value of 1 pip for 1 standard lot in account currency.
        Default 10.0 (USD account, major forex pairs, e.g. EURUSD).
        Use 1.0 for XAUUSD (100 oz/lot × $0.01/pip = $1/lot/pip).
    pip_factor:
        Price units per pip. Default 10_000 (4-decimal forex, 1 pip = 0.0001).
        Use 100 for XAUUSD and JPY pairs (2-decimal, 1 pip = 0.01).
    commission_per_lot:
        Round-trip commission deducted per lot traded. Default 7.0.
    variation:
        Strategy variation label (V1–V5). Stored in results for reference.
    """

    signal_params: "SignalParams | RsiSignalParams" = field(default_factory=SignalParams)
    initial_equity: float = 10_000.0
    risk_pct: float = 0.01
    pip_value: float = 10.0
    pip_factor: int = 10_000
    commission_per_lot: float = 7.0
    variation: str = "V1"
    timeframe: str = "H1"
    be_trigger_pct: float = 0.0  # 0 = disabled; e.g. 0.5 = move SL to entry at 50% of TP distance


@dataclass
class BacktestResult:
    """Aggregated metrics and per-trade log from a backtest run.

    Attributes
    ----------
    params:
        The :class:`BacktestParams` used.
    trades:
        DataFrame with one row per closed trade.
        Columns: ``entry_time``, ``exit_time``, ``direction``, ``lots``,
        ``entry_price``, ``exit_price``, ``pnl``, ``exit_reason``.
    equity_curve:
        Series of equity values indexed by bar timestamp.
    total_return_pct:
        Net return as a percentage of ``initial_equity``.
    sharpe_ratio:
        Annualised Sharpe Ratio (assumes H1 bars, risk-free rate 0).
    max_drawdown_pct:
        Maximum peak-to-trough equity drawdown as a percentage.
    win_rate:
        Fraction of trades that were profitable.
    profit_factor:
        Gross profit / gross loss.  ``inf`` when there are no losing trades.
    total_trades:
        Number of closed trades.
    """

    params: BacktestParams
    trades: pd.DataFrame
    equity_curve: pd.Series
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_backtest(
    df: pd.DataFrame,
    params: Optional[BacktestParams] = None,
) -> BacktestResult:
    """Run a vectorised backtest on an OHLCV DataFrame.

    Parameters
    ----------
    df:
        OHLCV DataFrame produced by :func:`algo_trading.data_feed.load_parquet`
        or :func:`algo_trading.data_feed.fetch_ohlcv`.
        Required columns: ``open``, ``high``, ``low``, ``close``.
    params:
        Backtest configuration. Uses :class:`BacktestParams` defaults when *None*.

    Returns
    -------
    BacktestResult
        Aggregated performance metrics and per-trade detail.

    Raises
    ------
    ValueError
        If ``df`` has fewer bars than ``slow_period`` + ``atr_period``.
    """
    if params is None:
        params = BacktestParams()

    sp = params.signal_params
    if isinstance(sp, RsiSignalParams):
        min_bars = sp.trend_ema_period + sp.atr_period
    else:
        min_bars = sp.slow_period + sp.atr_period
    if len(df) < min_bars:
        raise ValueError(
            f"DataFrame has only {len(df)} bars; need at least {min_bars} "
            "to produce valid signals."
        )

    # -- Generate signals (strategy dispatch) --------------------------------
    if isinstance(sp, RsiSignalParams):
        sig_df = generate_rsi_signals(df, sp)
    else:
        sig_df = generate_signals(df, sp)

    # -- Simulate bar-by-bar -------------------------------------------------
    equity = params.initial_equity
    equity_curve: list[tuple] = []

    open_trade: dict | None = None
    trades: list[dict] = []

    bars = sig_df.reset_index()  # flatten DatetimeIndex for integer iteration

    for i, row in bars.iterrows():
        # Check open trade exit conditions first (use bar's high/low)
        if open_trade is not None:
            direction = open_trade["direction"]
            lots = open_trade["lots"]
            entry = open_trade["entry_price"]

            # ── Break Even: move SL to entry once trigger price is reached ──
            if (
                params.be_trigger_pct > 0
                and not open_trade["be_activated"]
                and open_trade["be_trigger_price"] is not None
            ):
                if direction == 1 and row["high"] >= open_trade["be_trigger_price"]:
                    open_trade["sl_price"] = entry
                    open_trade["be_activated"] = True
                elif direction == -1 and row["low"] <= open_trade["be_trigger_price"]:
                    open_trade["sl_price"] = entry
                    open_trade["be_activated"] = True

            sl = open_trade["sl_price"]  # read after potential BE update
            tp = open_trade["tp_price"]

            exit_price: Optional[float] = None
            exit_reason = ""

            if direction == 1:  # long
                if row["low"] <= sl:
                    exit_price = sl
                    exit_reason = "BE" if open_trade["be_activated"] else "SL"
                elif row["high"] >= tp:
                    exit_price = tp
                    exit_reason = "TP"
            else:  # short
                if row["high"] >= sl:
                    exit_price = sl
                    exit_reason = "BE" if open_trade["be_activated"] else "SL"
                elif row["low"] <= tp:
                    exit_price = tp
                    exit_reason = "TP"

            if exit_price is not None:
                pips = (exit_price - entry) * direction * params.pip_factor
                pnl = pips * lots * params.pip_value - params.commission_per_lot * lots
                equity += pnl

                trades.append(
                    {
                        "entry_time": open_trade["entry_time"],
                        "exit_time": row["time"],
                        "direction": direction,
                        "lots": lots,
                        "entry_price": entry,
                        "sl_price": open_trade["sl_price"],
                        "tp_price": open_trade["tp_price"],
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "exit_reason": exit_reason,
                    }
                )
                open_trade = None

        # Open new trade on signal (next-bar-open execution, so we use row["open"])
        if open_trade is None and not np.isnan(sig_df.loc[sig_df.index[i], "signal"] if i < len(sig_df) else 0):
            signal_val = int(sig_df.iloc[i]["signal"])
            atr_val = sig_df.iloc[i]["atr"]

            if signal_val in (1, -1) and not np.isnan(atr_val):
                entry_price = row["open"]
                # Recalculate SL/TP from actual entry (next-bar open)
                sl_price = (
                    entry_price - params.signal_params.sl_atr_mult * atr_val
                    if signal_val == 1
                    else entry_price + params.signal_params.sl_atr_mult * atr_val
                )
                tp_price = (
                    entry_price + params.signal_params.tp_atr_mult * atr_val
                    if signal_val == 1
                    else entry_price - params.signal_params.tp_atr_mult * atr_val
                )
                sl_pips = abs(entry_price - sl_price) * params.pip_factor
                if sl_pips > 0:
                    from algo_trading.risk import position_size
                    from algo_trading.risk.risk import RiskParams
                    rp = RiskParams(risk_pct=params.risk_pct)
                    lots = position_size(equity, sl_pips, params.pip_value, rp)
                    be_trigger_price: Optional[float] = None
                    if params.be_trigger_pct > 0:
                        if signal_val == 1:
                            be_trigger_price = entry_price + params.be_trigger_pct * (tp_price - entry_price)
                        else:
                            be_trigger_price = entry_price - params.be_trigger_pct * (entry_price - tp_price)
                    open_trade = {
                        "entry_time": row["time"],
                        "direction": signal_val,
                        "lots": lots,
                        "entry_price": entry_price,
                        "sl_price": sl_price,
                        "tp_price": tp_price,
                        "be_trigger_price": be_trigger_price,
                        "be_activated": False,
                    }

        equity_curve.append((row["time"], equity))

    # Close any open trade at last bar's close (mark-to-market)
    if open_trade is not None:
        last_row = bars.iloc[-1]
        exit_price = last_row["close"]
        direction = open_trade["direction"]
        pips = (exit_price - open_trade["entry_price"]) * direction * params.pip_factor
        pnl = pips * open_trade["lots"] * params.pip_value - params.commission_per_lot * open_trade["lots"]
        equity += pnl
        trades.append(
            {
                "entry_time": open_trade["entry_time"],
                "exit_time": last_row["time"],
                "direction": direction,
                "lots": open_trade["lots"],
                "entry_price": open_trade["entry_price"],
                "sl_price": open_trade["sl_price"],
                "tp_price": open_trade["tp_price"],
                "exit_price": exit_price,
                "pnl": pnl,
                "exit_reason": "EOD",
            }
        )
        equity_curve[-1] = (equity_curve[-1][0], equity)

    # -- Build results -------------------------------------------------------
    trades_df = pd.DataFrame(trades) if trades else _empty_trades_df()
    eq_series = pd.Series(
        [v for _, v in equity_curve],
        index=pd.DatetimeIndex([t for t, _ in equity_curve]),
        name="equity",
    )

    total_return = (equity - params.initial_equity) / params.initial_equity * 100.0

    # Sharpe (annualised, scaled by actual timeframe)
    _BARS_PER_YEAR = {
        "M1": 525_600, "M5": 105_120, "M15": 35_040, "M30": 17_520,
        "M45": 11_680, "H1": 8_760, "H2": 4_380, "H4": 2_190, "D1": 252, "W1": 52,
    }
    if len(trades_df) > 1:
        ret_series = eq_series.pct_change().dropna()
        bars_per_year = _BARS_PER_YEAR.get(params.timeframe, 8_760)
        sharpe = (
            ret_series.mean() / ret_series.std() * (bars_per_year ** 0.5)
            if ret_series.std() > 0
            else 0.0
        )
    else:
        sharpe = 0.0

    # Max drawdown
    rolling_peak = eq_series.cummax()
    drawdown = (rolling_peak - eq_series) / rolling_peak
    max_dd = float(drawdown.max()) * 100.0

    # Win rate & profit factor
    if len(trades_df) > 0:
        winners = trades_df[trades_df["pnl"] > 0]
        losers = trades_df[trades_df["pnl"] <= 0]
        win_rate = len(winners) / len(trades_df)
        gross_profit = winners["pnl"].sum()
        gross_loss = abs(losers["pnl"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    else:
        win_rate = 0.0
        profit_factor = 0.0

    logger.info(
        "Backtest complete: %d trades, return=%.2f%%, sharpe=%.2f, max_dd=%.2f%%",
        len(trades_df),
        total_return,
        sharpe,
        max_dd,
    )

    return BacktestResult(
        params=params,
        trades=trades_df,
        equity_curve=eq_series,
        total_return_pct=round(total_return, 4),
        sharpe_ratio=round(float(sharpe), 4),
        max_drawdown_pct=round(max_dd, 4),
        win_rate=round(win_rate, 4),
        profit_factor=round(profit_factor, 4),
        total_trades=len(trades_df),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_trades_df() -> pd.DataFrame:
    """Return an empty trades DataFrame with the correct schema."""
    return pd.DataFrame(
        columns=[
            "entry_time",
            "exit_time",
            "direction",
            "lots",
            "entry_price",
            "sl_price",
            "tp_price",
            "exit_price",
            "pnl",
            "exit_reason",
        ]
    )
