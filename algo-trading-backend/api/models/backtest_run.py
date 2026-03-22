"""
backtest_run.py - ORM models for backtest run metadata and per-metric storage.

Two tables are defined:
- ``backtest_runs``: one row per backtest execution (params + summary metrics).
- ``backtest_metrics``: key-value pairs for detailed metrics per run, allowing
  schema-free metric additions without migrations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

if TYPE_CHECKING:
    from .trade import BacktestTrade


class BacktestRun(Base):
    """Metadata and summary statistics for a single backtest execution.

    Columns
    -------
    id:              UUID primary key.
    symbol:          Instrument tested, e.g. ``"XAUUSD"``.
    timeframe:       Bar timeframe string, e.g. ``"H1"``.
    variation:       Strategy variation label (V1–V5).
    start_date:      First bar date of the test window.
    end_date:        Last bar date of the test window.
    initial_equity:  Starting account equity.
    final_equity:    Equity at end of backtest.
    total_trades:    Total closed trades.
    win_rate:        Fraction of winning trades.
    profit_factor:   Gross profit / gross loss.
    total_return_pct: Net return as %.
    sharpe_ratio:    Annualised Sharpe.
    max_drawdown_pct: Peak-to-trough drawdown as %.
    params_json:     Full JSON snapshot of BacktestParams for reproducibility.
    created_at:      Timestamp when the run was persisted.
    metrics:         Relationship to :class:`BacktestMetric` rows.
    """

    __tablename__ = "backtest_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    variation: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    initial_equity: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    final_equity: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    profit_factor: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    total_return_pct: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown_pct: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    params_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # One-to-many: a run has many detail metric rows
    metrics: Mapped[list[BacktestMetric]] = relationship(
        "BacktestMetric",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # One-to-many: a run has many simulated trades
    trades: Mapped[list["BacktestTrade"]] = relationship(
        "BacktestTrade",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_backtest_runs_symbol_variation", "symbol", "variation"),
        Index("ix_backtest_runs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestRun id={self.id} symbol={self.symbol!r} "
            f"variation={self.variation!r} return={self.total_return_pct}%>"
        )


class BacktestMetric(Base):
    """Key-value store for granular per-run metrics and equity curve snapshots.

    Using a key-value table allows adding new metrics without schema changes.
    Equity curve data is stored as a JSON array for chart rendering.

    Columns
    -------
    id:         UUID primary key.
    run_id:     Foreign key to :class:`BacktestRun`.
    metric_key: Metric name, e.g. ``"sortino_ratio"`` or ``"equity_curve"``.
    value_num:  Numeric value (NULL for non-numeric metrics).
    value_json: JSON value for complex data (e.g. the equity curve array).
    run:        Back-reference to the parent :class:`BacktestRun`.
    """

    __tablename__ = "backtest_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backtest_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_num: Mapped[Optional[float]] = mapped_column(Numeric(18, 8), nullable=True)
    value_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    run: Mapped[BacktestRun] = relationship("BacktestRun", back_populates="metrics")

    __table_args__ = (
        Index("ix_backtest_metrics_run_key", "run_id", "metric_key", unique=True),
    )

    def __repr__(self) -> str:
        return f"<BacktestMetric run_id={self.run_id} key={self.metric_key!r}>"
