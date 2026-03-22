"""
executor.py - Live order execution via the MetaTrader 5 Python API.

Responsibilities
----------------
* Send market orders (buy/sell) with attached SL and TP to MT5.
* Close open positions by ticket number.
* Validate order results and raise structured errors on failure.

Safety guards
-------------
* All orders require an explicit SL price — zero-SL orders are rejected.
* Deviation is capped at a configurable slippage tolerance.
* Every MT5 interaction is logged at INFO level so the audit trail is complete.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5  # type: ignore[import]  — native Windows
    _MT5_AVAILABLE = True
except ImportError:
    try:
        from mt5linux import MetaTrader5 as mt5  # type: ignore[import]  — Linux via Wine socket
        _MT5_AVAILABLE = True
    except ImportError:
        mt5 = None  # type: ignore[assignment]
        _MT5_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderResult:
    """Outcome of a :func:`place_order` call.

    Attributes
    ----------
    ticket:
        MT5 position ticket assigned to the trade.
    symbol:
        Instrument traded.
    direction:
        ``1`` for long (buy), ``-1`` for short (sell).
    lots:
        Volume actually filled.
    entry_price:
        Average fill price.
    sl_price:
        Stop-loss price attached to the position.
    tp_price:
        Take-profit price attached to the position.
    comment:
        Free-text comment echoed back from MT5.
    """

    ticket: int
    symbol: str
    direction: int
    lots: float
    entry_price: float
    sl_price: float
    tp_price: float
    comment: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def place_order(
    symbol: str,
    direction: int,
    lots: float,
    sl_price: float,
    tp_price: float,
    *,
    comment: str = "AlgoTrader",
    deviation: int = 10,
    magic: int = 20240101,
) -> OrderResult:
    """Send a market order to MetaTrader 5.

    Parameters
    ----------
    symbol:
        MT5 symbol name, e.g. ``"XAUUSD"``.
    direction:
        ``1`` for a buy (long), ``-1`` for a sell (short).
    lots:
        Trade volume in lots (must be > 0).
    sl_price:
        Stop-loss price. Must differ from zero.
    tp_price:
        Take-profit price. Must differ from zero.
    comment:
        Order comment visible in MT5 terminal. Default ``"AlgoTrader"``.
    deviation:
        Maximum allowed slippage in points. Default 10.
    magic:
        Magic number to identify orders from this EA. Default 20240101.

    Returns
    -------
    OrderResult
        Filled order details.

    Raises
    ------
    RuntimeError
        If MT5 package is unavailable, initialisation fails, or the order
        is rejected by the broker.
    ValueError
        If ``direction`` is not ``1`` or ``-1``, or ``sl_price`` is zero.
    """
    _require_mt5()

    if direction not in (1, -1):
        raise ValueError(f"direction must be 1 (buy) or -1 (sell), got {direction}")
    if lots <= 0:
        raise ValueError(f"lots must be positive, got {lots}")
    if sl_price == 0:
        raise ValueError("sl_price must not be zero — all orders require a stop-loss.")

    order_type = mt5.ORDER_TYPE_BUY if direction == 1 else mt5.ORDER_TYPE_SELL

    # Fetch current price for sanity check
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Could not retrieve tick for {symbol}. Is it in Market Watch?")

    price = tick.ask if direction == 1 else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": order_type,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    logger.info(
        "Placing %s order: symbol=%s lots=%.2f price=%.5f sl=%.5f tp=%.5f",
        "BUY" if direction == 1 else "SELL",
        symbol,
        lots,
        price,
        sl_price,
        tp_price,
    )

    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        retcode = result.retcode if result else "N/A"
        comment_back = result.comment if result else "no result"
        raise RuntimeError(
            f"Order rejected by broker: retcode={retcode}, comment={comment_back!r}"
        )

    logger.info("Order filled: ticket=%d price=%.5f", result.order, result.price)

    return OrderResult(
        ticket=result.order,
        symbol=symbol,
        direction=direction,
        lots=lots,
        entry_price=result.price,
        sl_price=sl_price,
        tp_price=tp_price,
        comment=comment,
    )


def close_order(
    ticket: int,
    symbol: str,
    lots: float,
    direction: int,
    *,
    comment: str = "AlgoTrader-close",
    deviation: int = 10,
    magic: int = 20240101,
) -> dict:
    """Close an open MT5 position by ticket number.

    Sends a counter-order (sell for a long position, buy for a short) to
    flatten the specified ticket.

    Parameters
    ----------
    ticket:
        MT5 position ticket to close.
    symbol:
        Symbol of the position.
    lots:
        Volume to close (use the full position lots to close entirely).
    direction:
        Original direction of the trade: ``1`` = long, ``-1`` = short.
    comment:
        Order comment. Default ``"AlgoTrader-close"``.
    deviation:
        Max slippage in points.
    magic:
        Magic number.

    Returns
    -------
    dict
        ``{"ticket": ticket, "close_price": float, "retcode": int}``.

    Raises
    ------
    RuntimeError
        If MT5 is unavailable or the close order is rejected.
    """
    _require_mt5()

    close_type = mt5.ORDER_TYPE_SELL if direction == 1 else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Could not retrieve tick for {symbol}.")

    price = tick.bid if direction == 1 else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": deviation,
        "magic": magic,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    logger.info("Closing ticket=%d symbol=%s lots=%.2f", ticket, symbol, lots)
    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        retcode = result.retcode if result else "N/A"
        msg = result.comment if result else "no result"
        raise RuntimeError(f"Close order failed: retcode={retcode}, comment={msg!r}")

    logger.info("Position closed: ticket=%d close_price=%.5f", ticket, result.price)
    return {"ticket": ticket, "close_price": result.price, "retcode": result.retcode}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_mt5(host: str = "127.0.0.1", port: int = 18812) -> None:
    """Raise RuntimeError if MT5 package is not installed or terminal not connected.

    On Linux the ``mt5linux`` bridge is used; ``host`` and ``port`` are passed to
    ``mt5.initialize()`` to reach the Wine-based socket server.  On Windows those
    arguments are ignored and the native shared-memory connection is used instead.
    """
    import sys

    if not _MT5_AVAILABLE:
        raise RuntimeError(
            "Neither MetaTrader5 nor mt5linux is installed. "
            "On Windows: pip install MetaTrader5. "
            "On Linux: pip install mt5linux and start the Wine bridge server."
        )

    if sys.platform != "win32":
        ok = mt5.initialize(host=host, port=port)
    else:
        ok = mt5.initialize()

    if not ok:
        error = mt5.last_error()
        raise RuntimeError(f"MT5 terminal is not running or connection failed: {error}")
