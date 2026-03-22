"""
db.py - Async SQLAlchemy engine and session factory.

Creates a single module-level ``AsyncEngine`` from ``settings.DATABASE_URL``
and exposes ``get_db()`` as a FastAPI dependency that yields an
``AsyncSession`` with automatic commit-on-success and rollback-on-error.

Usage in a route::

    @router.get("/items")
    async def list_items(db: AsyncSession = Depends(get_db)):
        ...
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from configs.settings import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# ``echo`` is useful during development but should be False in production.
# Pool settings are tuned for a solo trading system (low concurrency).
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,  # detect stale connections before use
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep ORM objects usable after commit
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` for use as a FastAPI dependency.

    The session is automatically committed when the request completes
    successfully and rolled back on any exception.

    Yields
    ------
    AsyncSession
        An open database session bound to the module-level engine.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
