"""
schemas/trade.py - Pydantic models for the Trade resource.

Three layers follow the standard Pydantic separation pattern:

- ``TradeBase``   - shared fields present in every request and response.
- ``TradeCreate`` - fields accepted when creating a trade record via the API.
- ``TradeRead``   - full representation returned to the client, including
                    server-generated fields (id, created_at, updated_at).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TradeBase(BaseModel):
    """Fields shared by all trade schema variants."""

    backtest_run_id: uuid.UUID = Field(
        ..., description="UUID of the parent BacktestRun that generated this trade."
    )
    symbol: str = Field(..., max_length=20, examples=["XAUUSD"])
    direction: int = Field(..., ge=-1, le=1, examples=[1])
    lots: float = Field(..., gt=0, examples=[0.1])
    entry_price: float = Field(..., gt=0, examples=[2350.50])
    sl_price: float = Field(..., gt=0, examples=[2340.00])
    tp_price: float = Field(..., gt=0, examples=[2371.50])
    strategy: str = Field(default="MA_ATR", max_length=50)
    variation: str = Field(default="V1", max_length=10)


class TradeCreate(TradeBase):
    """Schema for creating a new trade record.

    Includes optional fields that are NULL for open trades.
    """

    entry_time: Optional[datetime] = Field(
        default=None,
        description="UTC datetime of entry. Defaults to server time when omitted.",
    )
    ticket: Optional[int] = Field(default=None, description="MT5 terminal ticket number.")
    notes: Optional[str] = Field(default=None, max_length=1000)


class TradeRead(TradeBase):
    """Full trade representation returned to API clients.

    Includes server-generated fields and exit information populated when
    the trade is closed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entry_time: datetime
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    ticket: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
