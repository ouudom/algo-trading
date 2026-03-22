"""
telegram.py - Fire-and-forget Telegram trade alert notifications.

Uses the Telegram Bot API via httpx (already in requirements).
All functions are async and silently swallow network errors so a Telegram
outage never interrupts the trading engine.

Configuration (set in .env):
    TELEGRAM_BOT_TOKEN  — token from @BotFather
    TELEGRAM_CHAT_ID    — target chat or channel ID

Usage::

    from src.algo_trading.notifications.telegram import notify_trade_opened
    await notify_trade_opened(symbol="XAUUSD", direction=1, lots=0.05, ...)
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _get_credentials() -> tuple[str, str]:
    """Return (bot_token, chat_id) from settings.  Returns empty strings if not set."""
    from configs.settings import get_settings
    s = get_settings()
    return s.TELEGRAM_BOT_TOKEN, s.TELEGRAM_CHAT_ID


async def send_telegram(message: str) -> None:
    """Send a plain-text Telegram message.

    Silently ignores all errors (network, invalid token, rate-limit) so the
    calling code never needs to handle Telegram-specific exceptions.
    """
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        logger.debug("Telegram not configured — skipping alert.")
        return

    url = _TELEGRAM_API.format(token=token)
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if not resp.is_success:
                logger.warning(
                    "Telegram API returned %d: %s", resp.status_code, resp.text[:200]
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send Telegram message: %s", exc)


async def notify_trade_opened(
    *,
    symbol: str,
    direction: int,
    lots: float,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    ticket: int,
    variation: str = "V1",
) -> None:
    """Alert: new live position opened."""
    side = "LONG" if direction == 1 else "SHORT"
    emoji = "" if direction == 1 else ""
    message = (
        f"{emoji} <b>{side} {symbol} opened</b>\n"
        f"Ticket: <code>{ticket}</code> | Variation: {variation}\n"
        f"Entry: <b>{entry_price:.5f}</b>  |  Lots: {lots:.2f}\n"
        f"SL: {sl_price:.5f}  |  TP: {tp_price:.5f}"
    )
    await send_telegram(message)


async def notify_trade_closed(
    *,
    symbol: str,
    direction: int,
    pnl: float,
    exit_reason: str,
    exit_price: float,
    ticket: int,
) -> None:
    """Alert: live position closed (SL, TP, or manual)."""
    side = "LONG" if direction == 1 else "SHORT"
    pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
    emoji = "" if pnl >= 0 else ""
    message = (
        f"{emoji} <b>{symbol} {side} closed ({exit_reason})</b>\n"
        f"Ticket: <code>{ticket}</code>\n"
        f"Exit: {exit_price:.5f}  |  PnL: <b>{pnl_str}</b>"
    )
    await send_telegram(message)


async def notify_circuit_breaker(
    *,
    reason: str,
    equity: float,
    symbol: Optional[str] = None,
) -> None:
    """Alert: circuit breaker triggered — trading halted."""
    sym_part = f" [{symbol}]" if symbol else ""
    message = (
        f" <b>CIRCUIT BREAKER triggered{sym_part}</b>\n"
        f"Reason: {reason}\n"
        f"Equity: ${equity:,.2f}  — trading halted\n"
        f"<i>Manual restart required.</i>"
    )
    await send_telegram(message)
