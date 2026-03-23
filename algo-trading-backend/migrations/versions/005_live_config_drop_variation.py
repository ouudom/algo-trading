"""drop variation from live_trading_configs, add params_json, update unique constraint

Revision ID: 005
Revises: 004
Create Date: 2026-03-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # 1. Drop the old unique constraint on (symbol, variation)
    op.drop_constraint(
        "uq_live_configs_symbol_variation", "live_trading_configs", type_="unique"
    )

    # 2. Drop variation column
    op.drop_column("live_trading_configs", "variation")

    # 3. Add params_json column (JSONB, nullable — filled with defaults on create)
    op.add_column(
        "live_trading_configs",
        sa.Column(
            "params_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # 4. Add new unique constraint on (symbol, strategy)
    op.create_unique_constraint(
        "uq_live_configs_symbol_strategy", "live_trading_configs", ["symbol", "strategy"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_live_configs_symbol_strategy", "live_trading_configs", type_="unique"
    )
    op.drop_column("live_trading_configs", "params_json")
    op.add_column(
        "live_trading_configs",
        sa.Column("variation", sa.String(10), nullable=True),
    )
    op.create_unique_constraint(
        "uq_live_configs_symbol_variation", "live_trading_configs", ["symbol", "variation"]
    )
