"""
routers/trades.py - Trade history endpoints.

Routes
------
GET  /trades/        - Paginated list of backtest trades with optional filters.
GET  /trades/{id}    - Single trade by UUID.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from api.deps import DBSession
from api.models.trade import BacktestTrade
from api.schemas.trade import TradeRead

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get(
    "/",
    response_model=list[TradeRead],
    summary="List trades",
    description=(
        "Return a paginated list of backtest trades, optionally filtered by "
        "backtest_run_id, symbol, strategy, or variation."
    ),
)
async def list_trades(
    db: DBSession,
    backtest_run_id: Optional[uuid.UUID] = Query(
        default=None, description="Filter by parent backtest run UUID"
    ),
    symbol: Optional[str] = Query(default=None, description="Filter by instrument symbol"),
    strategy: Optional[str] = Query(default=None, description="Filter by strategy label"),
    variation: Optional[str] = Query(default=None, description="Filter by variation label"),
    limit: int = Query(default=100, ge=1, le=500, description="Max rows to return"),
    offset: int = Query(default=0, ge=0, description="Row offset for pagination"),
) -> list[BacktestTrade]:
    """Return a list of backtest trade records ordered by entry_time descending."""
    stmt = (
        select(BacktestTrade)
        .order_by(BacktestTrade.entry_time.desc())
        .offset(offset)
        .limit(limit)
    )
    if backtest_run_id is not None:
        stmt = stmt.where(BacktestTrade.backtest_run_id == backtest_run_id)
    if symbol is not None:
        stmt = stmt.where(BacktestTrade.symbol == symbol.upper())
    if strategy is not None:
        stmt = stmt.where(BacktestTrade.strategy == strategy)
    if variation is not None:
        stmt = stmt.where(BacktestTrade.variation == variation)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/{trade_id}",
    response_model=TradeRead,
    summary="Get trade by ID",
    description="Return a single backtest trade record by its UUID.",
)
async def get_trade(trade_id: uuid.UUID, db: DBSession) -> BacktestTrade:
    """Return a single trade or raise 404."""
    stmt = select(BacktestTrade).where(BacktestTrade.id == trade_id)
    result = await db.execute(stmt)
    trade = result.scalar_one_or_none()

    if trade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade {trade_id} not found.",
        )
    return trade
