"""add backtest status column

Revision ID: 002
Revises: 001
Create Date: 2026-03-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "backtest_runs",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.create_index("ix_backtest_runs_status", "backtest_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_status", table_name="backtest_runs")
    op.drop_column("backtest_runs", "status")
