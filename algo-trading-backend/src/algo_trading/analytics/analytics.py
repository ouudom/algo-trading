"""
analytics.py - Post-trade and backtest performance analytics.

Computes standard quantitative trading metrics from a trades DataFrame or
an equity time-series, and builds the equity curve needed by the dashboard.

Typical usage::

    from algo_trading.analytics import compute_metrics, equity_curve

    result  = run_backtest(df)
    metrics = compute_metrics(result.trades, initial_equity=10_000)
    eq      = equity_curve(result.trades, initial_equity=10_000)
"""

from __future__ import annotations

import math
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# H1 bars per trading year (24 h/day × 365 days — FX/Gold trade near-continuously)
_BARS_PER_YEAR_H1 = 8_760


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_metrics(
    trades: pd.DataFrame,
    initial_equity: float = 10_000.0,
    bars_per_year: int = _BARS_PER_YEAR_H1,
) -> dict:
    """Compute a comprehensive set of performance metrics from a trades log.

    Parameters
    ----------
    trades:
        DataFrame with at minimum these columns:
        ``pnl`` (float), ``entry_time`` (datetime), ``exit_time`` (datetime).
        Produced by :func:`algo_trading.backtest.run_backtest` or
        :func:`algo_trading.journal.get_trades`.
    initial_equity:
        Starting account equity for return/drawdown calculations.
    bars_per_year:
        Annualisation factor.  Default 8 760 for H1 bars.

    Returns
    -------
    dict
        Keys:

        ==================  ====================================================
        Key                 Description
        ==================  ====================================================
        total_trades        Total number of closed trades
        win_rate            Fraction of trades with pnl > 0
        profit_factor       Gross profit / gross loss (inf if no losing trades)
        total_pnl           Sum of all pnl values
        avg_win             Average pnl of winning trades
        avg_loss            Average pnl of losing trades (negative value)
        max_consecutive_wins   Longest winning streak
        max_consecutive_losses Longest losing streak
        total_return_pct    Net return as % of initial_equity
        sharpe_ratio        Annualised Sharpe (risk-free rate = 0)
        sortino_ratio       Annualised Sortino using downside deviation
        max_drawdown_pct    Max peak-to-trough drawdown as %
        calmar_ratio        Annual return / max drawdown (0 if no drawdown)
        avg_trade_duration  Mean trade duration as a Timedelta string
        ==================  ====================================================

    Raises
    ------
    ValueError
        If ``trades`` is missing required columns.
    """
    _validate_trades(trades)

    if trades.empty:
        return _empty_metrics()

    pnl = trades["pnl"].astype(float)
    winners = pnl[pnl > 0]
    losers = pnl[pnl <= 0]

    total_pnl = float(pnl.sum())
    final_equity = initial_equity + total_pnl
    total_return_pct = (final_equity - initial_equity) / initial_equity * 100.0

    win_rate = len(winners) / len(pnl) if len(pnl) > 0 else 0.0
    gross_profit = float(winners.sum())
    gross_loss = float(abs(losers.sum()))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    avg_win = float(winners.mean()) if not winners.empty else 0.0
    avg_loss = float(losers.mean()) if not losers.empty else 0.0

    # Consecutive wins/losses
    max_consec_wins, max_consec_losses = _consecutive_streaks(pnl)

    # Equity curve for drawdown / Sharpe / Sortino
    eq = equity_curve(trades, initial_equity=initial_equity)
    ret = eq.pct_change().dropna()

    sharpe = _annualised_sharpe(ret, bars_per_year)
    sortino = _annualised_sortino(ret, bars_per_year)
    max_dd = _max_drawdown_pct(eq)
    calmar = (total_return_pct / 100.0) / (max_dd / 100.0) if max_dd > 0 else 0.0

    # Average trade duration
    if "entry_time" in trades.columns and "exit_time" in trades.columns:
        durations = pd.to_datetime(trades["exit_time"]) - pd.to_datetime(trades["entry_time"])
        avg_duration = str(durations.mean())
    else:
        avg_duration = "N/A"

    metrics = {
        "total_trades": len(trades),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4) if math.isfinite(profit_factor) else profit_factor,
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "total_return_pct": round(total_return_pct, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "calmar_ratio": round(calmar, 4),
        "avg_trade_duration": avg_duration,
    }

    logger.info("compute_metrics: %d trades, return=%.2f%%, sharpe=%.2f", len(trades), total_return_pct, sharpe)
    return metrics


def equity_curve(
    trades: pd.DataFrame,
    initial_equity: float = 10_000.0,
    freq: Optional[str] = None,
) -> pd.Series:
    """Build a cumulative equity curve from a trades DataFrame.

    The curve starts at ``initial_equity`` and steps up/down by each trade's
    ``pnl`` at the trade's ``exit_time``.

    Parameters
    ----------
    trades:
        Trades DataFrame with ``pnl`` and ``exit_time`` columns.
    initial_equity:
        Account equity before the first trade.
    freq:
        Optional pandas offset string (e.g. ``"1h"``) to resample the curve.
        When *None*, the curve has one point per trade exit.

    Returns
    -------
    pd.Series
        Equity values indexed by ``exit_time``, starting with ``initial_equity``
        at the first entry time (or index 0 if times are unavailable).

    Raises
    ------
    ValueError
        If required columns are missing.
    """
    _validate_trades(trades)

    if trades.empty:
        return pd.Series([initial_equity], name="equity")

    eq_df = trades[["exit_time", "pnl"]].copy()
    eq_df["exit_time"] = pd.to_datetime(eq_df["exit_time"])
    eq_df = eq_df.sort_values("exit_time")
    eq_df["equity"] = initial_equity + eq_df["pnl"].cumsum()

    series = eq_df.set_index("exit_time")["equity"]
    series.name = "equity"

    if freq is not None:
        # Forward-fill so the curve is continuous at the requested frequency
        series = series.resample(freq).last().ffill()

    return series


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_trades(trades: pd.DataFrame) -> None:
    required = {"pnl"}
    missing = required - set(trades.columns)
    if missing:
        raise ValueError(f"trades DataFrame is missing required columns: {missing}")


def _empty_metrics() -> dict:
    return {
        "total_trades": 0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "total_pnl": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "max_consecutive_wins": 0,
        "max_consecutive_losses": 0,
        "total_return_pct": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown_pct": 0.0,
        "calmar_ratio": 0.0,
        "avg_trade_duration": "N/A",
    }


def _annualised_sharpe(returns: pd.Series, bars_per_year: int) -> float:
    if returns.empty or returns.std() == 0:
        return 0.0
    return float(returns.mean() / returns.std() * math.sqrt(bars_per_year))


def _annualised_sortino(returns: pd.Series, bars_per_year: int) -> float:
    if returns.empty:
        return 0.0
    downside = returns[returns < 0]
    if downside.empty or downside.std() == 0:
        return float("inf")
    return float(returns.mean() / downside.std() * math.sqrt(bars_per_year))


def _max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    rolling_peak = equity.cummax()
    drawdown = (rolling_peak - equity) / rolling_peak
    return float(drawdown.max()) * 100.0


def _consecutive_streaks(pnl: pd.Series) -> tuple[int, int]:
    """Return (max_consecutive_wins, max_consecutive_losses)."""
    max_wins = max_losses = cur_wins = cur_losses = 0
    for p in pnl:
        if p > 0:
            cur_wins += 1
            cur_losses = 0
        else:
            cur_losses += 1
            cur_wins = 0
        max_wins = max(max_wins, cur_wins)
        max_losses = max(max_losses, cur_losses)
    return max_wins, max_losses
