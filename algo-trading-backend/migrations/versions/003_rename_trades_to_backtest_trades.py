"""rename trades to backtest_trades, add backtest_run_id FK

Revision ID: 003
Revises: 002
Create Date: 2026-03-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # 1. Rename table
    op.rename_table("trades", "backtest_trades")

    # 2. Rename inherited indexes to match new table name
    op.execute("ALTER INDEX ix_trades_id RENAME TO ix_backtest_trades_id")
    op.execute("ALTER INDEX ix_trades_symbol RENAME TO ix_backtest_trades_symbol")
    op.execute(
        "ALTER INDEX ix_trades_entry_time RENAME TO ix_backtest_trades_entry_time"
    )
    op.execute(
        "ALTER INDEX ix_trades_symbol_entry_time "
        "RENAME TO ix_backtest_trades_symbol_entry_time"
    )
    op.execute(
        "ALTER INDEX ix_trades_strategy_variation "
        "RENAME TO ix_backtest_trades_strategy_variation"
    )

    # 3. Add backtest_run_id column (nullable first to allow existing rows)
    op.add_column(
        "backtest_trades",
        sa.Column(
            "backtest_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # 4. Create FK constraint referencing backtest_runs.id
    op.create_foreign_key(
        "fk_backtest_trades_run_id",
        "backtest_trades",
        "backtest_runs",
        ["backtest_run_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 5. Create index on FK column
    op.create_index(
        "ix_backtest_trades_run_id",
        "backtest_trades",
        ["backtest_run_id"],
    )

    # 6. Tighten to NOT NULL (safe on dev/empty table; add backfill if migrating prod data)
    op.alter_column("backtest_trades", "backtest_run_id", nullable=False)


def downgrade() -> None:
    op.alter_column("backtest_trades", "backtest_run_id", nullable=True)
    op.drop_index("ix_backtest_trades_run_id", table_name="backtest_trades")
    op.drop_constraint(
        "fk_backtest_trades_run_id", "backtest_trades", type_="foreignkey"
    )
    op.drop_column("backtest_trades", "backtest_run_id")

    # Rename indexes back
    op.execute(
        "ALTER INDEX ix_backtest_trades_strategy_variation "
        "RENAME TO ix_trades_strategy_variation"
    )
    op.execute(
        "ALTER INDEX ix_backtest_trades_symbol_entry_time "
        "RENAME TO ix_trades_symbol_entry_time"
    )
    op.execute(
        "ALTER INDEX ix_backtest_trades_entry_time RENAME TO ix_trades_entry_time"
    )
    op.execute("ALTER INDEX ix_backtest_trades_symbol RENAME TO ix_trades_symbol")
    op.execute("ALTER INDEX ix_backtest_trades_id RENAME TO ix_trades_id")

    op.rename_table("backtest_trades", "trades")
