"""add live_trades and live_trading_configs tables

Revision ID: 004
Revises: 003
Create Date: 2026-03-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # live_trades — one row per MT5 live position
    # ------------------------------------------------------------------
    op.create_table(
        "live_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("strategy", sa.String(50), nullable=False, server_default="MA_ATR"),
        sa.Column("variation", sa.String(10), nullable=False, server_default="V1"),
        sa.Column("ticket", sa.Integer(), nullable=False),
        sa.Column("account_equity_at_entry", sa.Numeric(14, 2), nullable=True),
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
        sa.UniqueConstraint("ticket", name="uq_live_trades_ticket"),
    )
    op.create_index(op.f("ix_live_trades_id"), "live_trades", ["id"])
    op.create_index(op.f("ix_live_trades_symbol"), "live_trades", ["symbol"])
    op.create_index(op.f("ix_live_trades_entry_time"), "live_trades", ["entry_time"])
    op.create_index(op.f("ix_live_trades_ticket"), "live_trades", ["ticket"], unique=True)
    op.create_index(op.f("ix_live_trades_status"), "live_trades", ["status"])
    op.create_index(
        "ix_live_trades_symbol_status", "live_trades", ["symbol", "status"]
    )

    # ------------------------------------------------------------------
    # live_trading_configs — one row per symbol+variation config
    # ------------------------------------------------------------------
    op.create_table(
        "live_trading_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("variation", sa.String(10), nullable=False),
        sa.Column("strategy", sa.String(50), nullable=False, server_default="MA_ATR"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(30), nullable=False, server_default="idle"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_signal", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("peak_equity", sa.Numeric(14, 2), nullable=True),
        sa.Column("session_start_equity", sa.Numeric(14, 2), nullable=True),
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
        sa.UniqueConstraint("symbol", "variation", name="uq_live_configs_symbol_variation"),
    )
    op.create_index(op.f("ix_live_trading_configs_id"), "live_trading_configs", ["id"])
    op.create_index(
        op.f("ix_live_trading_configs_symbol"), "live_trading_configs", ["symbol"]
    )
    op.create_index(
        op.f("ix_live_trading_configs_enabled"), "live_trading_configs", ["enabled"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_live_trading_configs_enabled"), table_name="live_trading_configs")
    op.drop_index(op.f("ix_live_trading_configs_symbol"), table_name="live_trading_configs")
    op.drop_index(op.f("ix_live_trading_configs_id"), table_name="live_trading_configs")
    op.drop_table("live_trading_configs")

    op.drop_index("ix_live_trades_symbol_status", table_name="live_trades")
    op.drop_index(op.f("ix_live_trades_status"), table_name="live_trades")
    op.drop_index(op.f("ix_live_trades_ticket"), table_name="live_trades")
    op.drop_index(op.f("ix_live_trades_entry_time"), table_name="live_trades")
    op.drop_index(op.f("ix_live_trades_symbol"), table_name="live_trades")
    op.drop_index(op.f("ix_live_trades_id"), table_name="live_trades")
    op.drop_table("live_trades")
