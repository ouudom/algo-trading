"""
signal.py - MA Crossover + ATR Filter signal generation.

Strategy logic
--------------
1. Compute a fast EMA and a slow EMA over the close price.
2. Compute ATR(14) over the OHLCV bars.
3. A **long** signal fires when fast EMA crosses above slow EMA AND the
   candle's range (high - low) exceeds ``atr_multiplier * ATR``.
4. A **short** signal fires when fast EMA crosses below slow EMA AND the
   same ATR filter holds.
5. Otherwise the position is **flat**.

Stop-loss and take-profit are set symmetrically around the entry close:
    SL = close - (sl_atr_mult * ATR)   for longs
    TP = close + (tp_atr_mult * ATR)   for longs
    (reversed for shorts)

The output DataFrame carries all intermediate columns so downstream modules
(risk, backtest) can inspect them without recomputing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from algo_trading.indicators import atr, ema, rsi, sma


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class SignalParams:
    """Hyper-parameters for the MA-Crossover + ATR strategy.

    Attributes
    ----------
    fast_period:
        Look-back window for the fast EMA. Default 10.
    slow_period:
        Look-back window for the slow EMA. Default 50.
    atr_period:
        ATR smoothing period. Default 14.
    atr_multiplier:
        Minimum ATR multiple a candle range must exceed to confirm a signal.
        Set to 0.0 to disable the filter. Default 1.0.
    sl_atr_mult:
        Stop-loss distance as a multiple of ATR. Default 1.5.
    tp_atr_mult:
        Take-profit distance as a multiple of ATR. Default 3.0.
    sma200_period:
        Look-back window for the trend SMA. Default 200.
    use_sma200_filter:
        When True, long signals require close > SMA(sma200_period) and
        short signals require close < SMA(sma200_period). Default True.
    """

    fast_period: int = 10
    slow_period: int = 50
    atr_period: int = 14
    atr_multiplier: float = 1.0
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 3.0
    sma200_period: int = 200
    use_sma200_filter: bool = True


def generate_signals(
    df: pd.DataFrame,
    params: Optional[SignalParams] = None,
) -> pd.DataFrame:
    """Generate long/short/flat signals with SL and TP prices.

    Adds the following columns to a **copy** of ``df`` and returns it:

    ============  ============================================================
    Column        Description
    ============  ============================================================
    ema_fast      Fast EMA values
    ema_slow      Slow EMA values
    atr           ATR values
    sma200        SMA(sma200_period) trend filter (only when use_sma200_filter)
    signal        ``1`` = long, ``-1`` = short, ``0`` = flat / no trade
    sl_price      Stop-loss price for the signal bar (NaN when signal == 0)
    tp_price      Take-profit price for the signal bar (NaN when signal == 0)
    ============  ============================================================

    Parameters
    ----------
    df:
        OHLCV DataFrame with columns ``open``, ``high``, ``low``, ``close``,
        ``volume`` and a UTC DatetimeIndex.  Minimum required columns are
        ``high``, ``low``, ``close``.
    params:
        Strategy hyper-parameters.  Uses :class:`SignalParams` defaults when
        *None*.

    Returns
    -------
    pd.DataFrame
        Copy of ``df`` enriched with signal columns.

    Raises
    ------
    ValueError
        If required columns are missing or if fast_period >= slow_period.
    """
    if params is None:
        params = SignalParams()

    required = {"high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")

    if params.fast_period >= params.slow_period:
        raise ValueError(
            f"fast_period ({params.fast_period}) must be less than "
            f"slow_period ({params.slow_period})"
        )

    out = df.copy()

    # --- Indicators ---------------------------------------------------------
    out["ema_fast"] = ema(out["close"], params.fast_period)
    out["ema_slow"] = ema(out["close"], params.slow_period)
    out["atr"] = atr(out["high"], out["low"], out["close"], params.atr_period)

    # --- Optional SMA(200) trend filter ------------------------------------
    if params.use_sma200_filter:
        out["sma200"] = sma(out["close"], params.sma200_period)

    # --- Crossover detection ------------------------------------------------
    # fast crosses above slow: was below (or equal) on previous bar, above now
    cross_up = (out["ema_fast"].shift(1) <= out["ema_slow"].shift(1)) & (
        out["ema_fast"] > out["ema_slow"]
    )
    cross_down = (out["ema_fast"].shift(1) >= out["ema_slow"].shift(1)) & (
        out["ema_fast"] < out["ema_slow"]
    )

    # --- ATR volatility filter ----------------------------------------------
    candle_range = out["high"] - out["low"]
    atr_filter = candle_range >= (params.atr_multiplier * out["atr"])

    # --- Composite signal ---------------------------------------------------
    signal = pd.Series(0, index=out.index, dtype=np.int8)
    if params.use_sma200_filter:
        above_sma = out["close"] > out["sma200"]
        below_sma = out["close"] < out["sma200"]
        signal[cross_up & atr_filter & above_sma] = 1
        signal[cross_down & atr_filter & below_sma] = -1
    else:
        signal[cross_up & atr_filter] = 1
        signal[cross_down & atr_filter] = -1
    out["signal"] = signal

    # --- SL / TP prices -----------------------------------------------------
    out["sl_price"] = np.where(
        out["signal"] == 1,
        out["close"] - params.sl_atr_mult * out["atr"],
        np.where(
            out["signal"] == -1,
            out["close"] + params.sl_atr_mult * out["atr"],
            np.nan,
        ),
    )

    out["tp_price"] = np.where(
        out["signal"] == 1,
        out["close"] + params.tp_atr_mult * out["atr"],
        np.where(
            out["signal"] == -1,
            out["close"] - params.tp_atr_mult * out["atr"],
            np.nan,
        ),
    )

    n_long = int((out["signal"] == 1).sum())
    n_short = int((out["signal"] == -1).sum())
    import logging
    logging.getLogger(__name__).info(
        "generate_signals: %d long, %d short signals over %d bars",
        n_long,
        n_short,
        len(out),
    )

    return out


# ---------------------------------------------------------------------------
# RSI Momentum + Trend Filter strategy
# ---------------------------------------------------------------------------


@dataclass
class RsiSignalParams:
    """Hyper-parameters for the RSI Momentum + Trend Filter strategy.

    Attributes
    ----------
    rsi_period:
        RSI look-back window. Default 14.
    rsi_threshold:
        Level that RSI must cross to trigger a signal (above for long,
        below for short). Default 50.
    trend_ema_period:
        Period for the trend-direction EMA filter. Longs only fire when
        close > trend_ema; shorts only when close < trend_ema. Default 200.
    atr_period:
        ATR smoothing period used for SL/TP placement. Default 14.
    sl_atr_mult:
        Stop-loss distance as a multiple of ATR. Default 1.5.
    tp_atr_mult:
        Take-profit distance as a multiple of ATR. Default 3.0.
    """

    rsi_period: int = 14
    rsi_threshold: float = 50.0
    trend_ema_period: int = 200
    atr_period: int = 14
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 3.0


def generate_rsi_signals(
    df: pd.DataFrame,
    params: Optional[RsiSignalParams] = None,
) -> pd.DataFrame:
    """Generate RSI Momentum + Trend Filter signals with SL and TP prices.

    Adds the following columns to a **copy** of ``df`` and returns it:

    ============  ============================================================
    Column        Description
    ============  ============================================================
    rsi           RSI values
    trend_ema     Trend-direction EMA values
    atr           ATR values
    signal        ``1`` = long, ``-1`` = short, ``0`` = flat / no trade
    sl_price      Stop-loss price for the signal bar (NaN when signal == 0)
    tp_price      Take-profit price for the signal bar (NaN when signal == 0)
    ============  ============================================================

    Entry conditions
    ----------------
    Long:  RSI crosses **above** ``rsi_threshold`` AND close > trend_ema
    Short: RSI crosses **below** ``rsi_threshold`` AND close < trend_ema

    Parameters
    ----------
    df:
        OHLCV DataFrame with at minimum ``high``, ``low``, ``close`` columns
        and a UTC DatetimeIndex.
    params:
        Strategy hyper-parameters. Uses :class:`RsiSignalParams` defaults
        when *None*.

    Returns
    -------
    pd.DataFrame
        Copy of ``df`` enriched with signal columns.

    Raises
    ------
    ValueError
        If required columns are missing.
    """
    if params is None:
        params = RsiSignalParams()

    required = {"high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")

    out = df.copy()

    # --- Indicators ---------------------------------------------------------
    out["rsi"] = rsi(out["close"], params.rsi_period)
    out["trend_ema"] = ema(out["close"], params.trend_ema_period)
    out["atr"] = atr(out["high"], out["low"], out["close"], params.atr_period)

    # --- RSI crossover detection --------------------------------------------
    rsi_cross_up = (out["rsi"].shift(1) <= params.rsi_threshold) & (
        out["rsi"] > params.rsi_threshold
    )
    rsi_cross_down = (out["rsi"].shift(1) >= params.rsi_threshold) & (
        out["rsi"] < params.rsi_threshold
    )

    # --- Trend filter -------------------------------------------------------
    above_trend = out["close"] > out["trend_ema"]
    below_trend = out["close"] < out["trend_ema"]

    # --- Composite signal ---------------------------------------------------
    signal = pd.Series(0, index=out.index, dtype=np.int8)
    signal[rsi_cross_up & above_trend] = 1
    signal[rsi_cross_down & below_trend] = -1
    out["signal"] = signal

    # --- SL / TP prices -----------------------------------------------------
    out["sl_price"] = np.where(
        out["signal"] == 1,
        out["close"] - params.sl_atr_mult * out["atr"],
        np.where(
            out["signal"] == -1,
            out["close"] + params.sl_atr_mult * out["atr"],
            np.nan,
        ),
    )

    out["tp_price"] = np.where(
        out["signal"] == 1,
        out["close"] + params.tp_atr_mult * out["atr"],
        np.where(
            out["signal"] == -1,
            out["close"] - params.tp_atr_mult * out["atr"],
            np.nan,
        ),
    )

    import logging
    n_long = int((out["signal"] == 1).sum())
    n_short = int((out["signal"] == -1).sum())
    logging.getLogger(__name__).info(
        "generate_rsi_signals: %d long, %d short signals over %d bars",
        n_long,
        n_short,
        len(out),
    )

    return out
