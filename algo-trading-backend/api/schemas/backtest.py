"""
schemas/backtest.py - Pydantic models for BacktestRun and BacktestMetric resources.

``BacktestRunRead``        - summary representation of a backtest run.
``BacktestMetricRead``     - individual metric row returned for a run.
``BacktestRunRequest``     - request body for submitting a backtest job.
``BacktestSubmitResponse`` - response envelope for POST /backtests/run.
``BacktestStatusResponse`` - response envelope for GET /backtests/{id}/status.
``DataFileInfo``           - metadata for an uploaded Dukascopy CSV file.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BacktestMetricRead(BaseModel):
    """Pydantic representation of a single ``BacktestMetric`` row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    metric_key: str
    value_num: Optional[float] = None
    value_json: Optional[Any] = None


class BacktestRunRead(BaseModel):
    """Summary representation of a ``BacktestRun`` returned to API clients.

    The ``metrics`` list is populated via the ORM relationship and included
    by default for detailed endpoints (``GET /backtests/{id}``).
    For list endpoints the relationship is loaded as well because the ORM
    model uses ``lazy="selectin"``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    timeframe: str
    variation: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_equity: float
    final_equity: Optional[float] = None
    total_trades: int
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    total_return_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    params_json: Optional[dict] = None
    status: str = "pending"
    created_at: datetime
    metrics: list[BacktestMetricRead] = Field(default_factory=list)


class EquityPoint(BaseModel):
    """A single data point on an equity curve chart."""

    timestamp: datetime
    equity: float


class BacktestEquityCurveRead(BaseModel):
    """Equity curve payload returned by ``GET /backtests/{id}/equity``."""

    run_id: uuid.UUID
    initial_equity: float
    points: list[EquityPoint]


class BacktestRunRequest(BaseModel):
    """Request body for submitting an async backtest job via POST /backtests/run."""

    file_id: str
    symbol: str
    variation: str = "V1"
    strategy: str = Field(
        "ma_crossover",
        description="Strategy type: 'ma_crossover' or 'rsi_momentum'.",
    )
    timeframe: Optional[str] = Field(
        default=None,
        description=(
            "Target backtest timeframe, e.g. 'M5', 'H1'. "
            "When set, M1 source data is resampled before the backtest runs. "
            "Defaults to the file's native timeframe when omitted."
        ),
    )
    # MA Crossover params
    ema_fast: int = Field(20, ge=2)
    ema_slow: int = Field(50, ge=2)
    use_sma200_filter: bool = Field(
        True,
        description="When True, long signals require close > SMA(200); short signals require close < SMA(200).",
    )
    sma200_period: int = Field(200, ge=2, description="Look-back window for the SMA trend filter.")
    # RSI Momentum params (only used when strategy == 'rsi_momentum')
    rsi_period: Optional[int] = Field(None, ge=2)
    rsi_threshold: Optional[float] = Field(None, ge=0.0, le=100.0)
    trend_ema_period: Optional[int] = Field(None, ge=2)
    # Shared params
    atr_period: int = Field(14, ge=1)
    sl_multiplier: float = Field(1.5, gt=0)
    tp_multiplier: float = Field(3.0, gt=0)
    be_trigger_pct: float = Field(
        0.0, ge=0.0, lt=1.0,
        description="Fraction of TP distance at which SL is moved to entry (break even). 0 = disabled.",
    )
    start_date: Optional[str] = None   # ISO-8601 date string "YYYY-MM-DD"
    end_date: Optional[str] = None
    initial_equity: float = Field(10_000.0, gt=0)

    @model_validator(mode="after")
    def ema_fast_lt_slow(self) -> "BacktestRunRequest":
        if self.strategy == "ma_crossover" and self.ema_fast >= self.ema_slow:
            raise ValueError("ema_fast must be less than ema_slow")
        return self


class BacktestSubmitResponse(BaseModel):
    """Response returned immediately after submitting a backtest job."""

    run_id: str
    status: str


class BacktestStatusResponse(BaseModel):
    """Response for polling the status of a submitted backtest job."""

    run_id: str
    status: str
    progress_pct: float
    error: Optional[str] = None


class DataFileInfo(BaseModel):
    """Metadata for an uploaded Dukascopy CSV file."""

    file_id: str
    filename: str
    symbol: str
    timeframe: str
    bars: int
    date_from: str
    date_to: str
    uploaded_at: str
