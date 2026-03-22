"""
migrations/env.py - Alembic environment configuration.

Supports both:
- Offline mode (generates SQL without a live DB connection).
- Online async mode (applies migrations against a running PostgreSQL instance).

The DATABASE_URL is read from configs.settings so the same .env file drives
both the application and migrations.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

# ---------------------------------------------------------------------------
# Make project root importable so we can load settings and models
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# ---------------------------------------------------------------------------
# Alembic config object (gives access to alembic.ini values)
# ---------------------------------------------------------------------------
config = context.config

# Set up loggers as defined in alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import all ORM models so Alembic can detect them
# ---------------------------------------------------------------------------
from api.models.base import Base  # noqa: E402
import api.models.trade  # noqa: E402, F401
import api.models.backtest_run  # noqa: E402, F401

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Override sqlalchemy.url from application settings
# ---------------------------------------------------------------------------
from configs.settings import get_settings  # noqa: E402

_settings = get_settings()
# Alembic uses a sync connection for migrations; replace asyncpg with psycopg2
_sync_url = _settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
config.set_main_option("sqlalchemy.url", _sync_url)


# ---------------------------------------------------------------------------
# Offline migrations (generate SQL scripts without a live connection)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to the database."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online async migrations (apply directly against PostgreSQL)
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
