"""
test_indicators.py - Unit tests for algo_trading.indicators.

These tests have zero external dependencies (no database, no MT5, no network).
They verify the mathematical correctness and edge-case handling of:

- ema()
- atr()
- atr_rolling_mean()
- adx()

Reference values are computed inline so calculations are transparent and auditable.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from algo_trading.indicators import adx, atr, atr_rolling_mean, ema, sma

# ---------------------------------------------------------------------------
# Shared small dataset for hand-calculation tests (20 bars)
#
# Prices simulate a steady uptrend: close goes 100, 101, ..., 119.
# high = close + 1.5, low = close - 1.5  →  constant bar range of 3.0.
# With no gaps between bars the TR is dominated by high - low = 3.0.
# ---------------------------------------------------------------------------

_N = 20
_CLOSE = pd.Series([100.0 + i for i in range(_N)], dtype=float)
_HIGH = _CLOSE + 1.5
_LOW = _CLOSE - 1.5


# ---------------------------------------------------------------------------
# EMA tests
# ---------------------------------------------------------------------------


class TestEma:
    """Tests for the ema() function."""

    def test_matches_pandas_ewm_reference(self):
        """ema() must be byte-for-byte equivalent to pandas ewm(adjust=False)."""
        period = 5
        result = ema(_CLOSE, period)
        expected = _CLOSE.ewm(span=period, adjust=False).mean()
        expected.iloc[: period - 1] = float("nan")
        pd.testing.assert_series_equal(result, expected, check_names=False, atol=1e-10)

    def test_first_period_minus_one_are_nan(self):
        """The first period-1 values must be NaN (warm-up mask)."""
        period = 5
        result = ema(_CLOSE, period)
        assert result.iloc[: period - 1].isna().all()

    def test_first_valid_bar_is_not_nan(self):
        """The value at index period-1 must be finite (first valid bar)."""
        period = 5
        result = ema(_CLOSE, period)
        assert math.isfinite(result.iloc[period - 1])

    def test_raises_on_period_less_than_2(self):
        """period < 2 must raise ValueError mentioning 'period'."""
        with pytest.raises(ValueError, match="period"):
            ema(_CLOSE, 1)

    def test_monotone_increasing_on_uptrend(self):
        """EMA on a strict uptrend must be strictly increasing after warm-up."""
        period = 5
        result = ema(_CLOSE, period).dropna()
        diffs = result.diff().dropna()
        assert (diffs > 0).all()

    def test_same_index_as_input(self):
        """Output index must be identical to the input index."""
        idx = pd.date_range("2024-01-01", periods=_N, freq="1h", tz="UTC")
        series = pd.Series(_CLOSE.values, index=idx)
        result = ema(series, period=5)
        pd.testing.assert_index_equal(result.index, series.index)


# ---------------------------------------------------------------------------
# ATR tests
# ---------------------------------------------------------------------------


class TestAtr:
    """Tests for the atr() function."""

    def test_first_period_values_are_nan(self):
        """The first period values must be NaN (warm-up mask)."""
        period = 14
        result = atr(_HIGH, _LOW, _CLOSE, period=period)
        assert result.iloc[:period].isna().all()

    def test_first_valid_bar_is_not_nan(self):
        """The value at index period must be finite."""
        period = 3
        result = atr(_HIGH, _LOW, _CLOSE, period=period)
        assert math.isfinite(result.iloc[period])

    def test_values_always_positive(self):
        """All non-NaN ATR values must be strictly positive."""
        result = atr(_HIGH, _LOW, _CLOSE, period=5)
        assert (result.dropna() > 0).all()

    def test_matches_wilder_formula_constant_range(self):
        """With constant bar range 3.0 Wilder smoothing converges to 3.0.

        With period=3 and constant TR=3.0:
        - EWM alpha=1/3 on a constant input always returns that constant.
        - First valid bar (index=3) should equal 3.0 within floating-point tolerance.
        """
        period = 3
        result = atr(_HIGH, _LOW, _CLOSE, period=period)
        # First valid bar at index `period`
        assert result.iloc[period] == pytest.approx(3.0, abs=1e-6)

    def test_raises_on_period_less_than_1(self):
        """period < 1 must raise ValueError mentioning 'period'."""
        with pytest.raises(ValueError, match="period"):
            atr(_HIGH, _LOW, _CLOSE, period=0)

    def test_raises_on_mismatched_lengths(self):
        """Mismatched series lengths must raise ValueError mentioning 'same length'."""
        with pytest.raises(ValueError, match="same length"):
            atr(_HIGH, _LOW.iloc[:-1], _CLOSE, period=14)

    def test_result_name_is_set(self):
        """The result Series name must follow the ATR_<period> convention."""
        result = atr(_HIGH, _LOW, _CLOSE, period=14)
        assert result.name == "ATR_14"

    def test_same_index_as_input(self):
        """Output index must be identical to the input index."""
        idx = pd.date_range("2024-01-01", periods=_N, freq="1h", tz="UTC")
        h = pd.Series(_HIGH.values, index=idx)
        l = pd.Series(_LOW.values, index=idx)
        c = pd.Series(_CLOSE.values, index=idx)
        result = atr(h, l, c, period=5)
        pd.testing.assert_index_equal(result.index, idx)


# ---------------------------------------------------------------------------
# atr_rolling_mean tests
# ---------------------------------------------------------------------------


class TestAtrRollingMean:
    """Tests for the atr_rolling_mean() function."""

    def test_matches_pandas_rolling_mean(self):
        """atr_rolling_mean() must match pandas .rolling(window).mean() exactly."""
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        window = 3
        result = atr_rolling_mean(series, window)
        expected = series.rolling(window).mean()
        expected.iloc[: window - 1] = float("nan")
        # Expected values: NaN, NaN, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0
        pd.testing.assert_series_equal(result, expected, check_names=False, atol=1e-10)

    def test_first_window_minus_one_are_nan(self):
        """The first window-1 values must be NaN."""
        window = 5
        series = pd.Series(range(20), dtype=float)
        result = atr_rolling_mean(series, window)
        assert result.iloc[: window - 1].isna().all()

    def test_first_valid_bar_is_not_nan(self):
        """The value at index window-1 must be finite."""
        window = 5
        series = pd.Series(range(20), dtype=float)
        result = atr_rolling_mean(series, window)
        assert math.isfinite(result.iloc[window - 1])

    def test_raises_on_window_less_than_1(self):
        """window < 1 must raise ValueError mentioning 'window'."""
        with pytest.raises(ValueError, match="window"):
            atr_rolling_mean(pd.Series([1.0, 2.0, 3.0]), window=0)

    def test_series_name_is_set(self):
        """The result Series name must follow the ATR_RM_<window> convention."""
        result = atr_rolling_mean(pd.Series([1.0, 2.0, 3.0]), window=20)
        assert result.name == "ATR_RM_20"

    def test_same_index_as_input(self):
        """Output index must be identical to the input index."""
        idx = pd.date_range("2024-01-01", periods=10, freq="1h", tz="UTC")
        series = pd.Series(range(10), dtype=float, index=idx)
        result = atr_rolling_mean(series, window=3)
        pd.testing.assert_index_equal(result.index, idx)


# ---------------------------------------------------------------------------
# ADX tests
# ---------------------------------------------------------------------------


class TestAdx:
    """Tests for the adx() function."""

    def test_first_2_period_bars_are_nan(self):
        """The first 2*period values must be NaN (two smoothing layers)."""
        period = 14
        # Need at least 2*period+1 bars
        n = 2 * period + 10
        h = pd.Series([1000.0 + i * 2 for i in range(n)])
        l = pd.Series([999.0 + i * 2 for i in range(n)])
        c = pd.Series([999.5 + i * 2 for i in range(n)])
        result = adx(h, l, c, period=period)
        assert result.iloc[: 2 * period].isna().all()

    def test_values_bounded_0_to_100(self):
        """All non-NaN ADX values must lie in [0, 100]."""
        n = 60
        h = pd.Series([1000.0 + i * 2 + 5 for i in range(n)])
        l = pd.Series([1000.0 + i * 2 - 1 for i in range(n)])
        c = pd.Series([1000.0 + i * 2 for i in range(n)])
        result = adx(h, l, c, period=14)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_trending_data_gives_high_adx(self):
        """A strong, consistent uptrend should produce ADX > 25 after warm-up.

        Setup: 60 bars with close rising 2 points/bar, high 5 points above close
        (constant +DM dominance) and low only 1 point below close.
        """
        n = 60
        close = pd.Series([1000.0 + i * 2 for i in range(n)])
        high = close + 5.0
        low = close - 1.0
        result = adx(high, low, close, period=14)
        assert result.dropna().iloc[-1] > 25

    def test_choppy_data_gives_lower_adx_than_trending(self):
        """A choppy sideways market should produce lower ADX than a strong trend.

        A pure alternating zig-zag (close = 1000 ± 1 each bar) has no net
        directional movement, so ADX should remain substantially below the
        trending-market threshold of 25.
        """
        n = 60
        # Alternating close: 1001, 999, 1001, 999, ...
        close = pd.Series([1000.0 + (1 if i % 2 == 0 else -1) for i in range(n)])
        high = close + 1.5
        low = close - 1.5
        result_choppy = adx(high, low, close, period=14)

        # Compare with the trending result from test_trending_data_gives_high_adx
        n2 = 60
        close2 = pd.Series([1000.0 + i * 2 for i in range(n2)])
        high2 = close2 + 5.0
        low2 = close2 - 1.0
        result_trend = adx(high2, low2, close2, period=14)

        assert result_choppy.dropna().iloc[-1] < result_trend.dropna().iloc[-1]

    def test_raises_on_period_less_than_1(self):
        """period < 1 must raise ValueError mentioning 'period'."""
        with pytest.raises(ValueError, match="period"):
            adx(_HIGH, _LOW, _CLOSE, period=0)

    def test_raises_on_mismatched_lengths(self):
        """Mismatched series lengths must raise ValueError mentioning 'same length'."""
        with pytest.raises(ValueError, match="same length"):
            adx(_HIGH, _LOW.iloc[:-1], _CLOSE, period=14)

    def test_series_name_is_set(self):
        """The result Series name must follow the ADX_<period> convention."""
        result = adx(_HIGH, _LOW, _CLOSE, period=14)
        assert result.name == "ADX_14"

    def test_smoke_on_sample_ohlcv_df(self, sample_ohlcv_df):
        """ADX must run without error on realistic synthetic OHLCV data."""
        result = adx(
            sample_ohlcv_df["high"],
            sample_ohlcv_df["low"],
            sample_ohlcv_df["close"],
            period=14,
        )
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_ohlcv_df)
        # 200 bars > 2*14=28 warm-up → at least some valid values
        assert result.dropna().shape[0] > 0


# ---------------------------------------------------------------------------
# SMA tests
# ---------------------------------------------------------------------------


class TestSma:
    """Tests for the sma() function."""

    def test_matches_pandas_rolling_mean(self):
        """sma() must match pandas .rolling(window, min_periods=period).mean()."""
        period = 5
        result = sma(_CLOSE, period)
        expected = _CLOSE.rolling(window=period, min_periods=period).mean()
        pd.testing.assert_series_equal(result, expected, check_names=False, atol=1e-10)

    def test_first_period_minus_one_are_nan(self):
        """The first period-1 values must be NaN (warm-up)."""
        period = 5
        result = sma(_CLOSE, period)
        assert result.iloc[: period - 1].isna().all()

    def test_first_valid_bar_is_not_nan(self):
        """The value at index period-1 must be finite (first valid bar)."""
        period = 5
        result = sma(_CLOSE, period)
        assert math.isfinite(result.iloc[period - 1])

    def test_known_value(self):
        """sma(3) on [100, 101, 102, 103, 104] at index 2 must equal 101.0."""
        period = 3
        result = sma(_CLOSE, period)
        # SMA(3) at bar 2 = mean(100, 101, 102) = 101.0
        assert result.iloc[period - 1] == pytest.approx(101.0)

    def test_raises_on_period_less_than_2(self):
        """period < 2 must raise ValueError mentioning 'period'."""
        with pytest.raises(ValueError, match="period"):
            sma(_CLOSE, 1)

    def test_raises_on_series_shorter_than_period(self):
        """Series shorter than period must raise ValueError."""
        with pytest.raises(ValueError):
            sma(pd.Series([1.0, 2.0]), period=5)

    def test_series_name_is_set(self):
        """The result Series name must follow the SMA_<period> convention."""
        result = sma(_CLOSE, period=5)
        assert result.name == "SMA_5"

    def test_same_index_as_input(self):
        """Output index must be identical to the input index."""
        idx = pd.date_range("2024-01-01", periods=_N, freq="1h", tz="UTC")
        series = pd.Series(_CLOSE.values, index=idx)
        result = sma(series, period=5)
        pd.testing.assert_index_equal(result.index, series.index)

    def test_monotone_increasing_on_uptrend(self):
        """SMA on a strict uptrend must be strictly increasing after warm-up."""
        period = 5
        result = sma(_CLOSE, period).dropna()
        diffs = result.diff().dropna()
        assert (diffs > 0).all()
