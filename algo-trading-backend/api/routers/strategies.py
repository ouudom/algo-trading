"""
routers/strategies.py - Strategy catalogue endpoints.

Routes
------
GET  /strategies/   - Return the two supported strategies (EMA, RSI) with their
                      configurable parameters and defaults.
"""

from __future__ import annotations

from fastapi import APIRouter

from configs.settings import get_settings

router = APIRouter(prefix="/strategies", tags=["strategies"])

settings = get_settings()

# ---------------------------------------------------------------------------
# Strategy catalogue — EMA (MA Crossover + ATR) and RSI (Momentum + Trend)
# ---------------------------------------------------------------------------

STRATEGIES: list[dict] = [
    {
        "id": "EMA",
        "label": "EMA Crossover + ATR",
        "description": (
            "Fast EMA crosses above/below slow EMA, confirmed by candle range "
            "exceeding an ATR multiple. Optional SMA(200) trend filter."
        ),
        "params": [
            {"key": "fast_period",      "label": "Fast EMA Period",    "type": "int",   "default": 10,   "min": 2,   "max": 200},
            {"key": "slow_period",      "label": "Slow EMA Period",    "type": "int",   "default": 50,   "min": 5,   "max": 500},
            {"key": "atr_period",       "label": "ATR Period",         "type": "int",   "default": 14,   "min": 1,   "max": 100},
            {"key": "atr_multiplier",   "label": "ATR Multiplier",     "type": "float", "default": 1.0,  "min": 0.0, "max": 5.0, "step": 0.1},
            {"key": "sl_atr_mult",      "label": "SL × ATR",          "type": "float", "default": 1.5,  "min": 0.5, "max": 10.0, "step": 0.1},
            {"key": "tp_atr_mult",      "label": "TP × ATR",          "type": "float", "default": 3.0,  "min": 0.5, "max": 20.0, "step": 0.1},
            {"key": "use_sma200_filter","label": "SMA(200) Filter",    "type": "bool",  "default": True},
            {"key": "sma200_period",    "label": "SMA Period",         "type": "int",   "default": 200,  "min": 10,  "max": 500},
            {"key": "be_trigger_pct",   "label": "BE Trigger (0=off)", "type": "float", "default": 0.0,  "min": 0.0, "max": 0.99, "step": 0.05},
        ],
    },
    {
        "id": "RSI",
        "label": "RSI Momentum + Trend",
        "description": (
            "RSI crosses above/below a threshold, filtered by a trend EMA "
            "to only trade in the direction of the prevailing trend."
        ),
        "params": [
            {"key": "rsi_period",       "label": "RSI Period",         "type": "int",   "default": 14,   "min": 2,   "max": 100},
            {"key": "rsi_threshold",    "label": "RSI Threshold",      "type": "float", "default": 50.0, "min": 10.0,"max": 90.0, "step": 1.0},
            {"key": "trend_ema_period", "label": "Trend EMA Period",   "type": "int",   "default": 200,  "min": 10,  "max": 500},
            {"key": "atr_period",       "label": "ATR Period",         "type": "int",   "default": 14,   "min": 1,   "max": 100},
            {"key": "sl_atr_mult",      "label": "SL × ATR",          "type": "float", "default": 1.5,  "min": 0.5, "max": 10.0, "step": 0.1},
            {"key": "tp_atr_mult",      "label": "TP × ATR",          "type": "float", "default": 3.0,  "min": 0.5, "max": 20.0, "step": 0.1},
            {"key": "be_trigger_pct",   "label": "BE Trigger (0=off)", "type": "float", "default": 0.0,  "min": 0.0, "max": 0.99, "step": 0.05},
        ],
    },
]

# Convenient lookup by id
STRATEGY_DEFAULTS: dict[str, dict] = {
    s["id"]: {p["key"]: p["default"] for p in s["params"]}
    for s in STRATEGIES
}


@router.get(
    "/",
    summary="List strategies",
    description="Return the two supported strategies (EMA, RSI) with their configurable parameters.",
)
async def list_strategies() -> dict:
    """Return strategy metadata for the frontend strategy selector."""
    return {
        "supported_symbols": settings.SUPPORTED_SYMBOLS,
        "supported_timeframes": settings.SUPPORTED_TIMEFRAMES,
        "strategies": STRATEGIES,
    }
