"""
live_config.py - SQLAlchemy ORM model for live trading strategy configurations.

Each row represents one symbol + strategy combination that can be enabled or
disabled from the UI. Strategy parameters are stored as JSON so the user can
configure EMA or RSI params without schema changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class LiveTradingConfig(Base):
    """Live trading strategy configuration.

    Columns
    -------
    id:                    UUID primary key.
    symbol:                Instrument, e.g. ``"XAUUSD"``.
    strategy:              Strategy name: ``"EMA"`` or ``"RSI"``.
    params_json:           JSON dict of strategy parameters (overrides defaults).
    enabled:               Whether this config is currently active (job scheduled).
    status:                ``idle`` | ``running`` | ``halted_daily`` |
                           ``halted_drawdown`` | ``error``.
    last_run_at:           Timestamp of last bar processed.
    last_signal:           Last generated signal: ``1``, ``-1``, or ``0``.
    last_error:            Last error message if status is ``error``.
    peak_equity:           Rolling peak equity for drawdown circuit breaker.
    session_start_equity:  Equity at session start for daily loss check.
    created_at / updated_at: Row timestamps.
    """

    __tablename__ = "live_trading_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(10), nullable=False)  # "EMA" | "RSI"
    params_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="idle")
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_signal: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    peak_equity: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    session_start_equity: Mapped[Optional[float]] = mapped_column(
        Numeric(14, 2), nullable=True
    )

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
        UniqueConstraint("symbol", "strategy", name="uq_live_configs_symbol_strategy"),
    )

    def __repr__(self) -> str:
        return (
            f"<LiveTradingConfig id={self.id} symbol={self.symbol!r} "
            f"strategy={self.strategy!r} enabled={self.enabled} status={self.status!r}>"
        )
