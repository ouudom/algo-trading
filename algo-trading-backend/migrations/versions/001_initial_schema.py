"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-21

Creates the three core tables:
  - trades
  - backtest_runs
  - backtest_metrics
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # trades
    # ------------------------------------------------------------------
    op.create_table(
        "trades",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("direction", sa.Integer(), nullable=False),
        sa.Column("lots", sa.Numeric(10, 2), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("sl_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("tp_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_reason", sa.String(20), nullable=True),
        sa.Column("pnl", sa.Numeric(14, 4), nullable=True),
        sa.Column("strategy", sa.String(50), nullable=False),
        sa.Column("variation", sa.String(10), nullable=False),
        sa.Column("ticket", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_trades_id"), "trades", ["id"])
    op.create_index(op.f("ix_trades_symbol"), "trades", ["symbol"])
    op.create_index(op.f("ix_trades_entry_time"), "trades", ["entry_time"])
    op.create_index("ix_trades_symbol_entry_time", "trades", ["symbol", "entry_time"])
    op.create_index("ix_trades_strategy_variation", "trades", ["strategy", "variation"])

    # ------------------------------------------------------------------
    # backtest_runs
    # ------------------------------------------------------------------
    op.create_table(
        "backtest_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("variation", sa.String(10), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initial_equity", sa.Numeric(14, 2), nullable=False),
        sa.Column("final_equity", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("profit_factor", sa.Numeric(10, 4), nullable=True),
        sa.Column("total_return_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("max_drawdown_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_backtest_runs_id"), "backtest_runs", ["id"])
    op.create_index(op.f("ix_backtest_runs_symbol"), "backtest_runs", ["symbol"])
    op.create_index(op.f("ix_backtest_runs_variation"), "backtest_runs", ["variation"])
    op.create_index("ix_backtest_runs_symbol_variation", "backtest_runs", ["symbol", "variation"])
    op.create_index("ix_backtest_runs_created_at", "backtest_runs", ["created_at"])

    # ------------------------------------------------------------------
    # backtest_metrics
    # ------------------------------------------------------------------
    op.create_table(
        "backtest_metrics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("backtest_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_key", sa.String(100), nullable=False),
        sa.Column("value_num", sa.Numeric(18, 8), nullable=True),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(op.f("ix_backtest_metrics_run_id"), "backtest_metrics", ["run_id"])
    op.create_index(
        "ix_backtest_metrics_run_key",
        "backtest_metrics",
        ["run_id", "metric_key"],
        unique=True,
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("ix_backtest_metrics_run_key", table_name="backtest_metrics")
    op.drop_index(op.f("ix_backtest_metrics_run_id"), table_name="backtest_metrics")
    op.drop_table("backtest_metrics")

    op.drop_index("ix_backtest_runs_created_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_symbol_variation", table_name="backtest_runs")
    op.drop_index(op.f("ix_backtest_runs_variation"), table_name="backtest_runs")
    op.drop_index(op.f("ix_backtest_runs_symbol"), table_name="backtest_runs")
    op.drop_index(op.f("ix_backtest_runs_id"), table_name="backtest_runs")
    op.drop_table("backtest_runs")

    op.drop_index("ix_trades_strategy_variation", table_name="trades")
    op.drop_index("ix_trades_symbol_entry_time", table_name="trades")
    op.drop_index(op.f("ix_trades_entry_time"), table_name="trades")
    op.drop_index(op.f("ix_trades_symbol"), table_name="trades")
    op.drop_index(op.f("ix_trades_id"), table_name="trades")
    op.drop_table("trades")
