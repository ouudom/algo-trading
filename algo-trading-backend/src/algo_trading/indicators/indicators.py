"""
indicators.py - Vectorised technical indicators used by the MA-Crossover + ATR strategy.

All functions operate on ``pd.Series`` / ``pd.DataFrame`` objects and return
``pd.Series`` with the same index as the input, making them composable inside
a signal pipeline.

Available indicators
--------------------
ema(series, period)                        Exponential Moving Average
atr(high, low, close, period=14)           Average True Range (Wilder smoothing)
atr_rolling_mean(atr_series, window=20)    Rolling SMA of ATR (volatility gate)
sma(series, period)                        Simple Moving Average (trend filter)
adx(high, low, close, period=14)           Average Directional Index (trend strength)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate the Exponential Moving Average (EMA).

    Uses pandas' built-in EWM with ``span=period`` which implements the
    standard EMA formula:  EMA_t = price_t * k + EMA_{t-1} * (1 - k)
    where k = 2 / (period + 1).

    Parameters
    ----------
    series:
        A ``pd.Series`` of prices (typically ``close``).
    period:
        The look-back window (number of bars). Must be >= 2.

    Returns
    -------
    pd.Series
        EMA values with the same index as ``series``.
        The first ``period - 1`` values will be NaN (insufficient history).

    Raises
    ------
    ValueError
        If ``period`` is less than 2.

    Examples
    --------
    >>> close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    >>> ema(close, 3)
    0    1.000000
    1    1.500000
    2    2.250000
    3    3.125000
    4    4.062500
    dtype: float64
    """
    if period < 2:
        raise ValueError(f"EMA period must be >= 2, got {period}")

    result = series.ewm(span=period, adjust=False).mean()
    # Mask the warm-up period to be consistent with indicator libraries
    result.iloc[: period - 1] = float("nan")
    return result


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate the Average True Range (ATR) using Wilder smoothing.

    True Range is the greatest of:
    - high - low
    - |high - previous close|
    - |low  - previous close|

    ATR is the Wilder (RMA) smoothed average of True Range, equivalent to
    an EMA with ``alpha = 1 / period``.

    Parameters
    ----------
    high:
        Series of bar high prices.
    low:
        Series of bar low prices.
    close:
        Series of bar close prices (used to compute gaps from prior bar).
    period:
        Smoothing window length. Default is 14 (Wilder's original setting).

    Returns
    -------
    pd.Series
        ATR values indexed identically to the input series.
        The first ``period`` values will be NaN.

    Raises
    ------
    ValueError
        If ``period`` is less than 1 or if the input series have different lengths.

    Examples
    --------
    >>> import pandas as pd
    >>> high  = pd.Series([1.10, 1.20, 1.15, 1.25, 1.30])
    >>> low   = pd.Series([1.00, 1.05, 1.08, 1.12, 1.18])
    >>> close = pd.Series([1.05, 1.15, 1.12, 1.22, 1.28])
    >>> atr(high, low, close, period=3)
    """
    if period < 1:
        raise ValueError(f"ATR period must be >= 1, got {period}")
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high, low, and close series must have the same length.")

    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    # Wilder smoothing: RMA = EMA with alpha = 1/period
    atr_values = tr.ewm(alpha=1.0 / period, adjust=False).mean()

    # Mask warm-up: first bar has no prev_close, so TR[0] is unreliable;
    # mask the first `period` values so callers always get stable ATR.
    atr_values.iloc[:period] = float("nan")

    atr_values.name = f"ATR_{period}"
    return atr_values


def atr_rolling_mean(
    atr_series: pd.Series,
    window: int = 20,
) -> pd.Series:
    """Calculate a rolling Simple Moving Average of ATR values.

    Used as the volatility gate in the MA-Crossover strategy:
    a new position is only entered when ``ATR(14) > atr_rolling_mean(atr, 20)``,
    i.e. current volatility exceeds its recent average.

    Parameters
    ----------
    atr_series:
        A ``pd.Series`` of ATR values (output of :func:`atr`).
    window:
        The rolling look-back window. Default is 20 (bars).

    Returns
    -------
    pd.Series
        Rolling mean of ATR with the same index as ``atr_series``.
        The first ``window - 1`` values will be NaN.

    Raises
    ------
    ValueError
        If ``window`` is less than 1.
    """
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")

    result = atr_series.rolling(window=window).mean()
    result.iloc[: window - 1] = float("nan")
    result.name = f"ATR_RM_{window}"
    return result


def sma(series: pd.Series, period: int) -> pd.Series:
    """Calculate the Simple Moving Average (SMA).

    Uses pandas' rolling mean with ``min_periods=period`` so the first
    ``period - 1`` values are NaN (insufficient history).

    Parameters
    ----------
    series:
        A ``pd.Series`` of prices (typically ``close``).
    period:
        The look-back window (number of bars). Must be >= 2.

    Returns
    -------
    pd.Series
        SMA values with the same index as ``series``.
        The first ``period - 1`` values will be NaN (warm-up).

    Raises
    ------
    ValueError
        If ``period`` is less than 2 or the series is shorter than ``period``.

    Examples
    --------
    >>> close = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    >>> sma(close, 3)
    0    NaN
    1    NaN
    2    2.0
    3    3.0
    4    4.0
    dtype: float64
    """
    if period < 2:
        raise ValueError(f"SMA period must be >= 2, got {period}")
    if len(series) < period:
        raise ValueError(
            f"Series length ({len(series)}) is shorter than period ({period})."
        )

    result = series.rolling(window=period, min_periods=period).mean()
    result.name = f"SMA_{period}"
    return result


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate the Average Directional Index (ADX) using Wilder smoothing.

    ADX measures trend *strength* (not direction) on a 0–100 scale.
    Values above 25 indicate a trending market; the V5 strategy variant
    uses ``ADX > 25`` as an additional entry gate.

    Algorithm (Wilder's original):
    1. Compute True Range (identical to :func:`atr`).
    2. Compute +DM / -DM directional movement from consecutive bars.
    3. Wilder-smooth TR, +DM, -DM with ``alpha = 1 / period``.
    4. +DI = 100 × smoothed(+DM) / smoothed(TR)
       -DI = 100 × smoothed(-DM) / smoothed(TR)
    5. DX = 100 × |+DI - -DI| / (+DI + -DI)
    6. ADX = Wilder-smooth DX with ``alpha = 1 / period``.

    Parameters
    ----------
    high:
        Series of bar high prices.
    low:
        Series of bar low prices.
    close:
        Series of bar close prices.
    period:
        Smoothing window. Default is 14 (Wilder's original setting).

    Returns
    -------
    pd.Series
        ADX values indexed identically to the input series.
        The first ``2 * period`` values will be NaN (two smoothing layers).

    Raises
    ------
    ValueError
        If ``period`` is less than 1 or if the input series have different lengths.
    """
    if period < 1:
        raise ValueError(f"ADX period must be >= 1, got {period}")
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high, low, and close series must have the same length.")

    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    # True Range — same as atr()
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    # Directional Movement
    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=high.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )

    # Wilder smoothing for TR, +DM, -DM
    alpha = 1.0 / period
    smoothed_tr = tr.ewm(alpha=alpha, adjust=False).mean()
    smoothed_plus_dm = plus_dm.ewm(alpha=alpha, adjust=False).mean()
    smoothed_minus_dm = minus_dm.ewm(alpha=alpha, adjust=False).mean()

    # Directional Indicators
    plus_di = 100.0 * smoothed_plus_dm / smoothed_tr
    minus_di = 100.0 * smoothed_minus_dm / smoothed_tr

    # DX — guard against zero denominator
    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = pd.Series(
        np.where(di_sum == 0.0, 0.0, 100.0 * di_diff / di_sum),
        index=high.index,
    )

    # Wilder-smooth DX → ADX
    adx_values = dx.ewm(alpha=alpha, adjust=False).mean()

    # Mask warm-up: two smoothing layers require 2*period bars to stabilise
    adx_values.iloc[: 2 * period] = float("nan")
    adx_values.name = f"ADX_{period}"
    return adx_values


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate the Relative Strength Index (RSI) using Wilder smoothing.

    Uses Wilder's smoothed average (alpha = 1/period) for both average gain
    and average loss, which matches the behaviour of MT5 and TradingView.

    Parameters
    ----------
    series:
        A ``pd.Series`` of close prices.
    period:
        Look-back window. Default 14 (Wilder's original setting).

    Returns
    -------
    pd.Series
        RSI values in the range 0–100. First ``period`` values are NaN.

    Raises
    ------
    ValueError
        If ``period`` is less than 2.
    """
    if period < 2:
        raise ValueError(f"RSI period must be >= 2, got {period}")

    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)

    alpha = 1.0 / period
    avg_gain = up.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = down.ewm(alpha=alpha, adjust=False).mean()

    # Guard against division by zero (all-up-bar streaks)
    rs = avg_gain / avg_loss.replace(0.0, float("nan"))
    rsi_values = 100.0 - (100.0 / (1.0 + rs))

    rsi_values.iloc[:period] = float("nan")
    rsi_values.name = f"RSI_{period}"
    return rsi_values
