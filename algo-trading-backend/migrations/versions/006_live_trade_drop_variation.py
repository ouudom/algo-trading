"""drop variation column from live_trades

Revision ID: 006
Revises: 005
Create Date: 2026-03-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.drop_column("live_trades", "variation")
    # Update strategy column default to match new naming convention
    op.alter_column(
        "live_trades",
        "strategy",
        existing_type=sa.String(50),
        type_=sa.String(10),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "live_trades",
        "strategy",
        existing_type=sa.String(10),
        type_=sa.String(50),
        existing_nullable=False,
    )
    op.add_column(
        "live_trades",
        sa.Column("variation", sa.String(10), nullable=False, server_default="V1"),
    )
