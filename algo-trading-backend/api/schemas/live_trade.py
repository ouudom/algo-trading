"""
live_trade.py - Pydantic schemas for live trading API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Live Trade schemas
# ---------------------------------------------------------------------------


class LiveTradeRead(BaseModel):
    """Schema returned by GET /live-trades endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    direction: int
    lots: float
    entry_price: float
    sl_price: float
    tp_price: float
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    status: str
    strategy: str
    ticket: int
    account_equity_at_entry: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LiveStatsRead(BaseModel):
    """Aggregate statistics for live trades."""

    total_trades: int
    open_count: int
    closed_count: int
    win_count: int
    loss_count: int
    total_pnl: float
    today_pnl: float


# ---------------------------------------------------------------------------
# Live Config schemas
# ---------------------------------------------------------------------------


class LiveConfigCreate(BaseModel):
    """Request body for POST /live-trades/configs."""

    symbol: str = Field(..., min_length=2, max_length=20)
    strategy: str = Field(..., pattern=r"^(EMA|RSI)$")
    params_json: Optional[dict[str, Any]] = Field(default=None)


class LiveConfigUpdate(BaseModel):
    """Request body for PATCH /live-trades/configs/{id}."""

    params_json: Optional[dict[str, Any]] = Field(default=None)


class LiveConfigRead(BaseModel):
    """Schema returned by GET /live-trades/configs endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    strategy: str
    params_json: Optional[dict[str, Any]] = None
    enabled: bool
    status: str
    last_run_at: Optional[datetime] = None
    last_signal: Optional[int] = None
    last_error: Optional[str] = None
    peak_equity: Optional[float] = None
    session_start_equity: Optional[float] = None
    created_at: datetime
    updated_at: datetime
