"""
test_risk.py - Unit tests for algo_trading.risk.

These tests have zero external dependencies (no database, no MT5, no network).
They verify the mathematical correctness and edge-case handling of:

- position_size()
- check_daily_limit()
- check_drawdown_circuit()
"""

from __future__ import annotations

import math

import pytest

from algo_trading.risk.risk import RiskParams, check_daily_limit, check_drawdown_circuit, position_size


# ---------------------------------------------------------------------------
# position_size tests
# ---------------------------------------------------------------------------


class TestPositionSize:
    """Tests for the position_size() function."""

    def test_standard_calculation(self):
        """Risk 1 % of $10 000 with a 20-pip SL and $10/pip should give 0.5 lots."""
        lots = position_size(
            account_equity=10_000,
            stop_loss_pips=20,
            pip_value=10.0,
        )
        # risk_amount = 100; raw_lots = 100 / (20 * 10) = 0.5
        assert lots == pytest.approx(0.5, abs=1e-4)

    def test_risk_pct_scales_linearly(self):
        """Doubling risk_pct should double the lot size."""
        params_1pct = RiskParams(risk_pct=0.01)
        params_2pct = RiskParams(risk_pct=0.02)

        lots_1 = position_size(10_000, 20, 10.0, params=params_1pct)
        lots_2 = position_size(10_000, 20, 10.0, params=params_2pct)

        assert lots_2 == pytest.approx(lots_1 * 2, abs=0.01)

    def test_lots_clamped_to_min(self):
        """Very small equity / large SL should not go below min_lot."""
        params = RiskParams(risk_pct=0.001, min_lot=0.01)
        lots = position_size(
            account_equity=100,
            stop_loss_pips=500,
            pip_value=10.0,
            params=params,
        )
        assert lots == params.min_lot

    def test_lots_clamped_to_max(self):
        """Very large equity should not exceed max_lot."""
        params = RiskParams(risk_pct=0.10, max_lot=10.0)
        lots = position_size(
            account_equity=10_000_000,
            stop_loss_pips=1,
            pip_value=0.001,
            params=params,
        )
        assert lots == params.max_lot

    def test_lot_step_rounding(self):
        """Result should be a multiple of lot_step, rounded down."""
        params = RiskParams(risk_pct=0.01, lot_step=0.01)
        lots = position_size(10_000, 13, 10.0, params=params)
        # raw = 100 / 130 ≈ 0.7692 → rounded down to 0.76
        remainder = round(lots / params.lot_step - round(lots / params.lot_step), 8)
        assert remainder == pytest.approx(0.0, abs=1e-6)

    def test_raises_on_zero_equity(self):
        """Zero account_equity must raise ValueError."""
        with pytest.raises(ValueError, match="account_equity"):
            position_size(account_equity=0, stop_loss_pips=20, pip_value=10.0)

    def test_raises_on_negative_equity(self):
        """Negative account_equity must raise ValueError."""
        with pytest.raises(ValueError, match="account_equity"):
            position_size(account_equity=-100, stop_loss_pips=20, pip_value=10.0)

    def test_raises_on_zero_sl(self):
        """Zero stop_loss_pips must raise ValueError."""
        with pytest.raises(ValueError, match="stop_loss_pips"):
            position_size(account_equity=10_000, stop_loss_pips=0, pip_value=10.0)

    def test_raises_on_zero_pip_value(self):
        """Zero pip_value must raise ValueError."""
        with pytest.raises(ValueError, match="pip_value"):
            position_size(account_equity=10_000, stop_loss_pips=20, pip_value=0.0)

    def test_result_is_positive(self):
        """Lot size must always be positive under valid inputs."""
        lots = position_size(5_000, stop_loss_pips=30, pip_value=5.0)
        assert lots > 0

    def test_larger_sl_gives_smaller_size(self):
        """A wider SL means a smaller position to keep risk constant."""
        lots_tight = position_size(10_000, stop_loss_pips=10, pip_value=10.0)
        lots_wide = position_size(10_000, stop_loss_pips=50, pip_value=10.0)
        assert lots_tight > lots_wide


# ---------------------------------------------------------------------------
# check_daily_limit tests
# ---------------------------------------------------------------------------


class TestCheckDailyLimit:
    """Tests for check_daily_limit()."""

    def test_limit_not_breached_below_threshold(self):
        """2.5 % loss should not breach a 3 % daily limit."""
        # loss = 250, pct = 2.5 %
        assert check_daily_limit(10_000, 9_750) is False

    def test_limit_breached_above_threshold(self):
        """3.5 % loss should breach a 3 % daily limit."""
        # loss = 350, pct = 3.5 %
        assert check_daily_limit(10_000, 9_650) is True

    def test_limit_breached_at_exact_threshold(self):
        """Exactly 3 % loss should trigger the circuit breaker (>= comparison)."""
        assert check_daily_limit(10_000, 9_700) is True

    def test_no_loss_returns_false(self):
        """Flat or profitable session must not trigger the limit."""
        assert check_daily_limit(10_000, 10_000) is False
        assert check_daily_limit(10_000, 11_000) is False

    def test_custom_threshold(self):
        """Custom max_daily_loss_pct should be respected."""
        params = RiskParams(max_daily_loss_pct=0.05)
        # 4 % loss — below 5 % threshold
        assert check_daily_limit(10_000, 9_600, params=params) is False
        # 6 % loss — above 5 % threshold
        assert check_daily_limit(10_000, 9_400, params=params) is True

    def test_raises_on_zero_starting_equity(self):
        """Zero starting_equity must raise ValueError."""
        with pytest.raises(ValueError, match="starting_equity"):
            check_daily_limit(0, 9_000)


# ---------------------------------------------------------------------------
# check_drawdown_circuit tests
# ---------------------------------------------------------------------------


class TestCheckDrawdownCircuit:
    """Tests for check_drawdown_circuit()."""

    def test_circuit_not_triggered_below_threshold(self):
        """8.3 % drawdown from $12 000 peak should not breach 10 % threshold."""
        assert check_drawdown_circuit(12_000, 11_000) is False

    def test_circuit_triggered_above_threshold(self):
        """~10.8 % drawdown should breach the 10 % threshold."""
        assert check_drawdown_circuit(12_000, 10_700) is True

    def test_circuit_triggered_at_exact_threshold(self):
        """Exactly 10 % drawdown must trigger (>= comparison)."""
        assert check_drawdown_circuit(10_000, 9_000) is True

    def test_no_drawdown_returns_false(self):
        """Equity at or above peak must not trigger the circuit."""
        assert check_drawdown_circuit(10_000, 10_000) is False
        assert check_drawdown_circuit(10_000, 12_000) is False

    def test_custom_threshold(self):
        """Custom max_drawdown_pct should be respected."""
        params = RiskParams(max_drawdown_pct=0.20)
        # 15 % drawdown — below 20 %
        assert check_drawdown_circuit(10_000, 8_500, params=params) is False
        # 25 % drawdown — above 20 %
        assert check_drawdown_circuit(10_000, 7_500, params=params) is True

    def test_raises_on_zero_peak(self):
        """Zero peak_equity must raise ValueError."""
        with pytest.raises(ValueError, match="peak_equity"):
            check_drawdown_circuit(0, 5_000)
