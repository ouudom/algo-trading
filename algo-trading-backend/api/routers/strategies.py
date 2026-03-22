"""
routers/strategies.py - Strategy catalogue endpoints.

Routes
------
GET  /strategies/   - Return supported strategy configurations and variation catalogue.

This is a read-only, in-process endpoint backed by the settings module rather
than the database.  It gives the frontend everything it needs to build the
strategy selector without a separate round-trip.
"""

from __future__ import annotations

from fastapi import APIRouter

from configs.settings import get_settings

router = APIRouter(prefix="/strategies", tags=["strategies"])

settings = get_settings()

# ---------------------------------------------------------------------------
# Static variation catalogue — extend V1-V5 as needed.
# ---------------------------------------------------------------------------

_VARIATIONS: list[dict] = [
    {
        "id": "V1",
        "label": "Conservative",
        "description": "Slow EMA 50, Fast EMA 10, ATR 14, SL 1.5×ATR, TP 3×ATR, SMA(200) filter ON",
        "params": {
            "fast_period": 10,
            "slow_period": 50,
            "atr_period": 14,
            "atr_multiplier": 1.0,
            "sl_atr_mult": 1.5,
            "tp_atr_mult": 3.0,
            "sma200_period": 200,
            "use_sma200_filter": True,
        },
    },
    {
        "id": "V2",
        "label": "Moderate",
        "description": "Slow EMA 30, Fast EMA 8, ATR 14, SL 1.2×ATR, TP 2.5×ATR, SMA(200) filter ON",
        "params": {
            "fast_period": 8,
            "slow_period": 30,
            "atr_period": 14,
            "atr_multiplier": 0.8,
            "sl_atr_mult": 1.2,
            "tp_atr_mult": 2.5,
            "sma200_period": 200,
            "use_sma200_filter": True,
        },
    },
    {
        "id": "V3",
        "label": "Aggressive",
        "description": "Slow EMA 20, Fast EMA 5, ATR 10, SL 1×ATR, TP 2×ATR, SMA(200) filter ON",
        "params": {
            "fast_period": 5,
            "slow_period": 20,
            "atr_period": 10,
            "atr_multiplier": 0.5,
            "sl_atr_mult": 1.0,
            "tp_atr_mult": 2.0,
            "sma200_period": 200,
            "use_sma200_filter": True,
        },
    },
    {
        "id": "V4",
        "label": "Trend-follower",
        "description": "Slow EMA 100, Fast EMA 20, ATR 20, SL 2×ATR, TP 4×ATR, SMA(200) filter ON",
        "params": {
            "fast_period": 20,
            "slow_period": 100,
            "atr_period": 20,
            "atr_multiplier": 1.2,
            "sl_atr_mult": 2.0,
            "tp_atr_mult": 4.0,
            "sma200_period": 200,
            "use_sma200_filter": True,
        },
    },
    {
        "id": "V5",
        "label": "Scalper",
        "description": "Slow EMA 15, Fast EMA 3, ATR 7, SL 0.8×ATR, TP 1.6×ATR, SMA(200) filter OFF",
        "params": {
            "fast_period": 3,
            "slow_period": 15,
            "atr_period": 7,
            "atr_multiplier": 0.3,
            "sl_atr_mult": 0.8,
            "tp_atr_mult": 1.6,
            "sma200_period": 200,
            "use_sma200_filter": False,
        },
    },
]


@router.get(
    "/",
    summary="List strategies",
    description="Return the full catalogue of supported strategy variations and their parameters.",
)
async def list_strategies() -> dict:
    """Return strategy metadata for the frontend strategy selector."""
    return {
        "strategy": "MA_ATR_Crossover",
        "description": (
            "Moving Average Crossover with ATR volatility filter and SMA(200) trend filter. "
            "Signals fire on EMA crossovers confirmed by candle range exceeding a multiple of ATR, "
            "filtered by the 200-period SMA trend direction."
        ),
        "supported_symbols": settings.SUPPORTED_SYMBOLS,
        "supported_timeframes": settings.SUPPORTED_TIMEFRAMES,
        "trading_mode": settings.TRADING_MODE,
        "variations": _VARIATIONS,
    }
