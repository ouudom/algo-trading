"""
journal.py - Async trade journaling via SQLAlchemy 2.x.

Every trade produced by a backtest run is persisted to the
``backtest_trades`` table so that analytics, dashboards, and post-trade
reviews have a reliable source of truth.

Usage example::

    async with async_session() as session:
        trade_id = await log_trade(session, backtest_run_id=run_id, symbol="XAUUSD", ...)
        trades   = await get_trades(session, backtest_run_id=run_id, limit=100)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def log_trade(
    session: AsyncSession,
    *,
    backtest_run_id: UUID,
    symbol: str,
    direction: int,
    lots: float,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    entry_time: Optional[datetime] = None,
    exit_price: Optional[float] = None,
    exit_time: Optional[datetime] = None,
    exit_reason: Optional[str] = None,
    pnl: Optional[float] = None,
    strategy: str = "MA_ATR",
    variation: str = "V1",
    ticket: Optional[int] = None,
    notes: Optional[str] = None,
) -> UUID:
    """Persist a backtest trade record to the database.

    Parameters
    ----------
    session:
        Active ``AsyncSession``.  The caller is responsible for committing.
    backtest_run_id:
        UUID of the parent ``BacktestRun`` that generated this trade.
    symbol:
        Traded instrument, e.g. ``"XAUUSD"``.
    direction:
        ``1`` for long, ``-1`` for short.
    lots:
        Filled volume.
    entry_price:
        Actual fill price at entry.
    sl_price:
        Stop-loss price.
    tp_price:
        Take-profit price.
    entry_time:
        Datetime of entry. Defaults to ``datetime.now(UTC)`` when *None*.
    exit_price:
        Fill price at close. *None* for open trades.
    exit_time:
        Datetime of close. *None* for open trades.
    exit_reason:
        One of ``"SL"``, ``"TP"``, ``"manual"``, ``"EOD"``.
    pnl:
        Realised P&L in account currency (after commission).
    strategy:
        Strategy name label.
    variation:
        Hyper-parameter variation label (V1–V5).
    ticket:
        MT5 ticket number (NULL for backtest trades).
    notes:
        Optional free-text notes.

    Returns
    -------
    UUID
        The UUID primary key of the newly created trade record.

    Raises
    ------
    ValueError
        If ``direction`` is not ``1`` or ``-1``.
    """
    # Import here to avoid circular imports at module load time
    from api.models.trade import BacktestTrade  # type: ignore[import]

    if direction not in (1, -1):
        raise ValueError(f"direction must be 1 or -1, got {direction}")

    now_utc = datetime.now(timezone.utc)
    trade = BacktestTrade(
        backtest_run_id=backtest_run_id,
        symbol=symbol,
        direction=direction,
        lots=lots,
        entry_price=entry_price,
        sl_price=sl_price,
        tp_price=tp_price,
        entry_time=entry_time or now_utc,
        exit_price=exit_price,
        exit_time=exit_time,
        exit_reason=exit_reason,
        pnl=pnl,
        strategy=strategy,
        variation=variation,
        ticket=ticket,
        notes=notes,
    )

    session.add(trade)
    await session.flush()  # populates trade.id without committing

    logger.info(
        "Logged trade id=%s symbol=%s direction=%d lots=%.2f",
        trade.id,
        symbol,
        direction,
        lots,
    )
    return trade.id


# ---------------------------------------------------------------------------
# Live trade journaling
# ---------------------------------------------------------------------------


async def open_live_trade(
    session: AsyncSession,
    *,
    symbol: str,
    direction: int,
    lots: float,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    ticket: int,
    account_equity_at_entry: Optional[float] = None,
    entry_time: Optional[datetime] = None,
    strategy: str = "MA_ATR",
    variation: str = "V1",
    notes: Optional[str] = None,
) -> UUID:
    """Persist a new live position to the database with status='open'.

    Parameters
    ----------
    session:
        Active ``AsyncSession``.  Caller is responsible for committing.
    ticket:
        MT5 ticket number — must be unique across all live trades.
    account_equity_at_entry:
        Account equity snapshot at the time of entry, used for risk auditing.

    Returns
    -------
    UUID
        Primary key of the newly created ``LiveTrade`` row.

    Raises
    ------
    ValueError
        If ``direction`` is not ``1`` or ``-1``.
    """
    from api.models.live_trade import LiveTrade  # type: ignore[import]

    if direction not in (1, -1):
        raise ValueError(f"direction must be 1 or -1, got {direction}")

    trade = LiveTrade(
        symbol=symbol,
        direction=direction,
        lots=lots,
        entry_price=entry_price,
        sl_price=sl_price,
        tp_price=tp_price,
        entry_time=entry_time or datetime.now(timezone.utc),
        status="open",
        strategy=strategy,
        variation=variation,
        ticket=ticket,
        account_equity_at_entry=account_equity_at_entry,
        notes=notes,
    )

    session.add(trade)
    await session.flush()

    logger.info(
        "Opened live trade id=%s symbol=%s direction=%d ticket=%d lots=%.2f",
        trade.id,
        symbol,
        direction,
        ticket,
        lots,
    )
    return trade.id


async def close_live_trade(
    session: AsyncSession,
    *,
    ticket: int,
    exit_price: float,
    pnl: float,
    exit_reason: str,
    exit_time: Optional[datetime] = None,
) -> UUID:
    """Mark an open live trade as closed.

    Parameters
    ----------
    ticket:
        MT5 ticket number identifying the position to close.
    exit_price:
        Actual fill price at close.
    pnl:
        Realised profit/loss in account currency.
    exit_reason:
        One of ``"SL"``, ``"TP"``, ``"manual"``, ``"circuit_break"``.
    exit_time:
        Datetime of close. Defaults to ``datetime.now(UTC)``.

    Returns
    -------
    UUID
        Primary key of the updated ``LiveTrade`` row.

    Raises
    ------
    LookupError
        If no live trade with the given ticket is found.
    ValueError
        If the trade's status is not ``"open"``.
    """
    from api.models.live_trade import LiveTrade  # type: ignore[import]

    stmt = select(LiveTrade).where(LiveTrade.ticket == ticket)
    result = await session.execute(stmt)
    trade = result.scalar_one_or_none()

    if trade is None:
        raise LookupError(f"No live trade found with ticket={ticket}")
    if trade.status != "open":
        raise ValueError(
            f"Live trade ticket={ticket} has status={trade.status!r}, expected 'open'"
        )

    trade.exit_price = exit_price
    trade.pnl = pnl
    trade.exit_reason = exit_reason
    trade.exit_time = exit_time or datetime.now(timezone.utc)
    trade.status = "closed"

    await session.flush()

    logger.info(
        "Closed live trade id=%s ticket=%d exit_reason=%s pnl=%.2f",
        trade.id,
        ticket,
        exit_reason,
        pnl,
    )
    return trade.id


async def get_open_positions(
    session: AsyncSession,
    *,
    symbol: Optional[str] = None,
) -> list:
    """Return all live trades with status='open'.

    Used as a deduplication guard before entering a new position — the live
    trading loop skips signal processing if an open position already exists
    for the requested symbol.

    Parameters
    ----------
    symbol:
        When provided, filters to positions for that symbol only.

    Returns
    -------
    list[LiveTrade]
        ORM ``LiveTrade`` instances with status ``"open"``.
    """
    from api.models.live_trade import LiveTrade  # type: ignore[import]

    stmt = select(LiveTrade).where(LiveTrade.status == "open")
    if symbol is not None:
        stmt = stmt.where(LiveTrade.symbol == symbol)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_live_trades(
    session: AsyncSession,
    *,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list:
    """Retrieve live trade records ordered by entry_time descending.

    Parameters
    ----------
    symbol:
        Filter by instrument when provided.
    status:
        Filter by status (``"open"``, ``"closed"``, ``"error"``) when provided.
    limit:
        Maximum rows to return.
    offset:
        Pagination offset.

    Returns
    -------
    list[LiveTrade]
    """
    from api.models.live_trade import LiveTrade  # type: ignore[import]

    stmt = (
        select(LiveTrade)
        .order_by(LiveTrade.entry_time.desc())
        .offset(offset)
        .limit(limit)
    )
    if symbol is not None:
        stmt = stmt.where(LiveTrade.symbol == symbol)
    if status is not None:
        stmt = stmt.where(LiveTrade.status == status)

    result = await session.execute(stmt)
    trades = result.scalars().all()

    logger.debug("get_live_trades returned %d records", len(trades))
    return list(trades)


async def get_trades(
    session: AsyncSession,
    *,
    backtest_run_id: Optional[UUID] = None,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    variation: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list:
    """Retrieve backtest trade records from the database.

    Parameters
    ----------
    session:
        Active ``AsyncSession``.
    backtest_run_id:
        Filter by parent backtest run when provided.
    symbol:
        Filter by symbol when provided.
    strategy:
        Filter by strategy label when provided.
    variation:
        Filter by variation label when provided.
    limit:
        Maximum number of rows to return. Default 100.
    offset:
        Row offset for pagination. Default 0.

    Returns
    -------
    list[BacktestTrade]
        ORM ``BacktestTrade`` instances ordered by ``entry_time`` descending.
    """
    from api.models.trade import BacktestTrade  # type: ignore[import]

    stmt = (
        select(BacktestTrade)
        .order_by(BacktestTrade.entry_time.desc())
        .offset(offset)
        .limit(limit)
    )

    if backtest_run_id is not None:
        stmt = stmt.where(BacktestTrade.backtest_run_id == backtest_run_id)
    if symbol is not None:
        stmt = stmt.where(BacktestTrade.symbol == symbol)
    if strategy is not None:
        stmt = stmt.where(BacktestTrade.strategy == strategy)
    if variation is not None:
        stmt = stmt.where(BacktestTrade.variation == variation)

    result = await session.execute(stmt)
    trades = result.scalars().all()

    logger.debug("get_trades returned %d records", len(trades))
    return list(trades)
