"""
conftest.py - Shared pytest fixtures for the AlgoTrader test suite.

Fixtures
--------
event_loop:       Provide a fresh asyncio event loop per test session.
test_engine:      In-memory SQLite async engine (no PostgreSQL needed in CI).
test_session:     AsyncSession bound to the test engine, auto-rolled back.
test_client:      HTTPX async test client for FastAPI integration tests.
sample_ohlcv_df:  A small synthetic OHLCV DataFrame for unit tests.

Usage::

    async def test_something(test_session: AsyncSession):
        ...

    async def test_api(test_client: AsyncClient):
        response = await test_client.get("/health")
        assert response.status_code == 200
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Event loop — one per session to avoid "loop is closed" errors
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Provide a session-scoped asyncio event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Test database (SQLite in-memory via aiosqlite — no PostgreSQL needed)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create all tables in an in-memory SQLite DB and yield the engine."""
    from api.models.base import Base  # noqa: F401 — ensure models are imported
    import api.models.trade  # noqa: F401
    import api.models.backtest_run  # noqa: F401

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional AsyncSession that rolls back after each test."""
    factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an HTTPX AsyncClient wired to the FastAPI app with a test DB."""
    from api.main import app
    from api.deps import get_db

    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Synthetic OHLCV data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    """Return a 200-bar synthetic OHLCV DataFrame for unit/integration tests.

    The series is constructed with a mild upward trend and random noise so
    EMA crossovers will occur at least once.
    """
    import numpy as np

    rng = np.random.default_rng(seed=42)
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")

    close = 2000.0 + np.cumsum(rng.normal(0.5, 5.0, n))
    high = close + rng.uniform(1.0, 10.0, n)
    low = close - rng.uniform(1.0, 10.0, n)
    open_ = close - rng.normal(0.0, 3.0, n)
    volume = rng.integers(100, 1000, n).astype(float)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )
