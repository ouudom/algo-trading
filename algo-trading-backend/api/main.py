"""
main.py - FastAPI application entrypoint.

Configures:
- CORS for the Next.js frontend (localhost:3000 in development)
- Global exception handler returning consistent JSON error envelopes
- API routers for trades, backtests, and strategies
- Health-check endpoint at GET /health

Start with::

    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import backtests, data as data_router, live_trades, strategies, trades
from api.scheduler import scheduler
from configs.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


async def _restore_live_jobs() -> None:
    """Re-schedule APScheduler jobs for any configs that were enabled at shutdown.

    Silently skips if the live_trading_configs table does not exist yet
    (i.e. migration 004 has not been applied).
    """
    from api.db import AsyncSessionLocal
    from api.models.live_config import LiveTradingConfig
    from api.routers.live_trades import _add_scheduler_job
    from sqlalchemy import select, text

    try:
        async with AsyncSessionLocal() as session:
            # Check the table exists before querying it
            check = await session.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'live_trading_configs' LIMIT 1"
                )
            )
            if check.fetchone() is None:
                logger.warning(
                    "live_trading_configs table not found — run 'alembic upgrade head'. "
                    "Live trading jobs will not be restored."
                )
                return

            result = await session.execute(
                select(LiveTradingConfig).where(LiveTradingConfig.enabled == True)  # noqa: E712
            )
            configs = result.scalars().all()
            for config in configs:
                _add_scheduler_job(str(config.id), config.symbol, config.variation)
                logger.info(
                    "Restored live job for %s %s on startup.", config.symbol, config.variation
                )
    except Exception as exc:
        logger.warning("Could not restore live jobs on startup: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Application startup and shutdown hooks."""
    logger.info("AlgoTrader API starting up — environment: %s", settings.TRADING_MODE)
    scheduler.start()
    await _restore_live_jobs()
    yield
    scheduler.shutdown(wait=False)
    logger.info("AlgoTrader API shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AlgoTrader API",
    description=(
        "Backend REST API for the AlgoTrader algorithmic trading system. "
        "Exposes trade history, backtest results, and strategy configuration."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

ALLOWED_ORIGINS = [
    "http://localhost:3000",    # Next.js dev server
    "http://127.0.0.1:3000",
]

if settings.CORS_ORIGINS:
    ALLOWED_ORIGINS.extend(settings.CORS_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a JSON error envelope instead of a 500 HTML traceback."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred.",
            "type": type(exc).__name__,
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(trades.router, prefix="/api/v1")
app.include_router(backtests.router, prefix="/api/v1")
app.include_router(strategies.router, prefix="/api/v1")
app.include_router(data_router.router, prefix="/api/v1")
app.include_router(live_trades.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Utility endpoints
# ---------------------------------------------------------------------------


@app.get("/health", tags=["system"], summary="Health check")
async def health() -> dict[str, Any]:
    """Return service health status.

    Used by load balancers and monitoring systems to verify the API is alive.
    """
    return {"status": "ok", "version": app.version}


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "AlgoTrader API — see /docs for documentation."}
