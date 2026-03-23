"""
live_trade.py - SQLAlchemy ORM model for live MT5 trade positions.

Each row represents a single real-money position placed via MT5.
Unlike backtest trades, live trades have a mandatory MT5 ticket number and
a status column to distinguish open from closed positions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class LiveTrade(Base):
    """Represents a single live MT5 position.

    Columns
    -------
    id:                      UUID primary key.
    symbol:                  Traded instrument, e.g. ``"XAUUSD"``.
    direction:               ``1`` = long, ``-1`` = short.
    lots:                    Trade volume in lots.
    entry_price:             Fill price at entry.
    sl_price:                Stop-loss price.
    tp_price:                Take-profit price.
    entry_time:              UTC datetime of trade entry.
    exit_price:              Fill price at close.  NULL while open.
    exit_time:               UTC datetime of close.  NULL while open.
    exit_reason:             ``SL`` | ``TP`` | ``manual`` | ``circuit_break``.
    pnl:                     Realised P&L in account currency.
    status:                  ``open`` | ``closed`` | ``error``.
    strategy:                Strategy name: ``"EMA"`` or ``"RSI"``.
    ticket:                  MT5 ticket number — unique and NOT NULL.
    account_equity_at_entry: Account equity snapshot at entry (risk audit).
    notes:                   Optional free-text annotation.
    created_at / updated_at: Row timestamps.
    """

    __tablename__ = "live_trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[int] = mapped_column(Integer, nullable=False)
    lots: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    sl_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    tp_price: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    exit_price: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    exit_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exit_reason: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    strategy: Mapped[str] = mapped_column(String(10), nullable=False, default="EMA")
    ticket: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_equity_at_entry: Mapped[Optional[float]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("ticket", name="uq_live_trades_ticket"),
        Index("ix_live_trades_symbol_status", "symbol", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<LiveTrade id={self.id} symbol={self.symbol!r} "
            f"ticket={self.ticket} status={self.status!r} pnl={self.pnl}>"
        )
