"""
risk.py - Position sizing and trading circuit-breakers.

Design philosophy
-----------------
* Fixed fractional risk per trade: never risk more than ``risk_pct`` of the
  current account equity on a single trade.
* Daily loss limit: halt trading once realised P&L for the session breaches
  ``max_daily_loss_pct`` of starting equity.
* Drawdown circuit-breaker: suspend trading when equity drawdown from the
  rolling peak exceeds ``max_drawdown_pct``.

All functions are pure (no side-effects) so they are trivially unit-testable
and can be used in both live and backtest contexts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskParams:
    """Risk management configuration.

    Attributes
    ----------
    risk_pct:
        Fraction of account equity to risk per trade (e.g. 0.01 = 1 %).
    max_daily_loss_pct:
        Maximum cumulative loss for the session as a fraction of starting
        equity (e.g. 0.03 = 3 %).  Triggers :func:`check_daily_limit`.
    max_drawdown_pct:
        Maximum equity drawdown from the rolling peak as a fraction
        (e.g. 0.10 = 10 %).  Triggers :func:`check_drawdown_circuit`.
    min_lot:
        Minimum tradeable lot size for the broker. Default 0.01.
    max_lot:
        Maximum lot size cap. Default 10.0.
    lot_step:
        Lot rounding granularity. Default 0.01.
    """

    risk_pct: float = 0.01
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.10
    min_lot: float = 0.01
    max_lot: float = 10.0
    lot_step: float = 0.01


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def position_size(
    account_equity: float,
    stop_loss_pips: float,
    pip_value: float,
    params: Optional[RiskParams] = None,
) -> float:
    """Calculate the lot size that risks exactly ``risk_pct`` of equity.

    Formula::

        lots = (account_equity * risk_pct) / (stop_loss_pips * pip_value_per_lot)

    The result is clamped to ``[min_lot, max_lot]`` and rounded down to the
    nearest ``lot_step``.

    Parameters
    ----------
    account_equity:
        Current account balance / equity in account currency.
    stop_loss_pips:
        Distance from entry to stop-loss in pips (must be > 0).
    pip_value:
        Monetary value of 1 pip for 1 standard lot in account currency.
        For XAUUSD at $1 per pip per lot, pass ``1.0``.
        For EURUSD with a USD account, typically ``10.0`` per standard lot.
    params:
        Risk configuration.  Uses :class:`RiskParams` defaults when *None*.

    Returns
    -------
    float
        Lot size, rounded to ``lot_step`` precision and within
        ``[min_lot, max_lot]``.

    Raises
    ------
    ValueError
        If ``account_equity``, ``stop_loss_pips``, or ``pip_value`` are not
        positive numbers.

    Examples
    --------
    >>> # Risk 1 % of $10 000 with a 20-pip SL and $10/pip value
    >>> position_size(10_000, stop_loss_pips=20, pip_value=10.0)
    0.5
    """
    if params is None:
        params = RiskParams()

    if account_equity <= 0:
        raise ValueError(f"account_equity must be positive, got {account_equity}")
    if stop_loss_pips <= 0:
        raise ValueError(f"stop_loss_pips must be positive, got {stop_loss_pips}")
    if pip_value <= 0:
        raise ValueError(f"pip_value must be positive, got {pip_value}")

    risk_amount = account_equity * params.risk_pct
    raw_lots = risk_amount / (stop_loss_pips * pip_value)

    # Round down to lot_step
    import math
    rounded = math.floor(raw_lots / params.lot_step) * params.lot_step

    # Clamp to broker limits
    clamped = max(params.min_lot, min(params.max_lot, rounded))

    # Final precision clean-up to avoid floating-point noise (e.g. 0.49999...)
    precision = len(str(params.lot_step).rstrip("0").split(".")[-1])
    return round(clamped, precision)


def check_daily_limit(
    starting_equity: float,
    current_equity: float,
    params: Optional[RiskParams] = None,
) -> bool:
    """Return ``True`` if the daily loss limit has been breached.

    The system should stop opening new positions when this returns ``True``.

    Parameters
    ----------
    starting_equity:
        Account equity at the start of the trading session / day.
    current_equity:
        Current account equity.
    params:
        Risk configuration.  Uses :class:`RiskParams` defaults when *None*.

    Returns
    -------
    bool
        ``True`` if ``(starting - current) / starting >= max_daily_loss_pct``.

    Raises
    ------
    ValueError
        If ``starting_equity`` is not positive.

    Examples
    --------
    >>> check_daily_limit(10_000, 9_650)   # 3.5 % loss, default limit 3 %
    True
    >>> check_daily_limit(10_000, 9_750)   # 2.5 % loss
    False
    """
    if params is None:
        params = RiskParams()

    if starting_equity <= 0:
        raise ValueError(f"starting_equity must be positive, got {starting_equity}")

    daily_loss_pct = (starting_equity - current_equity) / starting_equity
    return daily_loss_pct >= params.max_daily_loss_pct


def check_drawdown_circuit(
    peak_equity: float,
    current_equity: float,
    params: Optional[RiskParams] = None,
) -> bool:
    """Return ``True`` if the drawdown circuit-breaker has been triggered.

    Compares the current equity against the highest observed equity since
    the strategy started (or since the last reset).

    Parameters
    ----------
    peak_equity:
        The highest account equity observed in the current run.
    current_equity:
        Current account equity.
    params:
        Risk configuration.  Uses :class:`RiskParams` defaults when *None*.

    Returns
    -------
    bool
        ``True`` if ``(peak - current) / peak >= max_drawdown_pct``.

    Raises
    ------
    ValueError
        If ``peak_equity`` is not positive.

    Examples
    --------
    >>> check_drawdown_circuit(12_000, 10_700)  # ~10.8 % drawdown
    True
    >>> check_drawdown_circuit(12_000, 11_000)  # 8.3 % drawdown
    False
    """
    if params is None:
        params = RiskParams()

    if peak_equity <= 0:
        raise ValueError(f"peak_equity must be positive, got {peak_equity}")

    drawdown_pct = (peak_equity - current_equity) / peak_equity
    return drawdown_pct >= params.max_drawdown_pct
