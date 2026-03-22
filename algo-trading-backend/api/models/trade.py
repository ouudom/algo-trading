"""
trade.py - SQLAlchemy ORM model for individual backtest trade records.

Every trade produced by a backtest run is stored as a single row in the
``backtest_trades`` table.  Each row is linked to its parent ``BacktestRun``
via ``backtest_run_id``.  The model uses the SQLAlchemy 2.x ``Mapped[T]`` +
``mapped_column()`` annotation style.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

if TYPE_CHECKING:
    from .backtest_run import BacktestRun


class BacktestTrade(Base):
    """Represents a single simulated trade produced by a backtest run.

    Columns
    -------
    id:              UUID primary key (PostgreSQL native UUID).
    backtest_run_id: FK to ``backtest_runs.id`` — owning run (CASCADE delete).
    symbol:          Traded instrument, e.g. ``"XAUUSD"``.
    direction:       ``1`` = long, ``-1`` = short.
    lots:            Trade volume in lots.
    entry_price:     Fill price at entry.
    sl_price:        Stop-loss price.
    tp_price:        Take-profit price.
    entry_time:      UTC datetime of trade entry.
    exit_price:      Fill price at close.  NULL while trade is open.
    exit_time:       UTC datetime of trade close.  NULL while open.
    exit_reason:     One of ``SL``, ``TP``, ``manual``, ``EOD``.
    pnl:             Realised P&L after commission, in account currency.
    strategy:        Strategy label, e.g. ``"MA_ATR"``.
    variation:       Hyper-parameter variation, e.g. ``"V1"``.
    ticket:          MT5 terminal ticket number for cross-reference (NULL for backtest trades).
    notes:           Optional free-text annotation.
    created_at:      Row creation timestamp (server default).
    updated_at:      Row update timestamp (auto-updated).
    """

    __tablename__ = "backtest_trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtest_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    strategy: Mapped[str] = mapped_column(String(50), nullable=False, default="MA_ATR")
    variation: Mapped[str] = mapped_column(String(10), nullable=False, default="V1")
    ticket: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship back to the owning BacktestRun
    run: Mapped["BacktestRun"] = relationship("BacktestRun", back_populates="trades")

    # Composite indexes for common query patterns
    __table_args__ = (
        Index("ix_backtest_trades_symbol_entry_time", "symbol", "entry_time"),
        Index("ix_backtest_trades_strategy_variation", "strategy", "variation"),
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestTrade id={self.id} symbol={self.symbol!r} "
            f"run_id={self.backtest_run_id} pnl={self.pnl}>"
        )
