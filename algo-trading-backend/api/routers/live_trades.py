"""
live_trades.py - FastAPI router for live trading configuration and trade history.

Endpoints
---------
Config management:
    GET    /live-trades/configs              List all configs
    POST   /live-trades/configs              Create a config
    PATCH  /live-trades/configs/{id}         Update params
    DELETE /live-trades/configs/{id}         Delete a config

Enable / disable (controls APScheduler job):
    POST   /live-trades/configs/{id}/enable  Start live trading for this config
    POST   /live-trades/configs/{id}/disable Stop live trading for this config

Trade history:
    GET    /live-trades/                     List all live trades (paginated)
    GET    /live-trades/open                 Open positions only
    GET    /live-trades/stats                Aggregate statistics
    GET    /live-trades/{trade_id}           Single trade by UUID
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, date
from typing import Optional

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from api.db import AsyncSessionLocal
from api.deps import DBSession
from api.models.live_config import LiveTradingConfig
from api.models.live_trade import LiveTrade
from api.routers.strategies import STRATEGY_DEFAULTS
from api.scheduler import scheduler
from api.schemas.live_trade import (
    LiveConfigCreate,
    LiveConfigRead,
    LiveConfigUpdate,
    LiveStatsRead,
    LiveTradeRead,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live-trades", tags=["live-trades"])

# ---------------------------------------------------------------------------
# In-memory peak-equity tracking (keyed by config_id str)
# Persisted to DB on each bar so it survives restarts.
# ---------------------------------------------------------------------------
_peak_equity: dict[str, float] = {}


# ---------------------------------------------------------------------------
# Signal dispatch helpers
# ---------------------------------------------------------------------------


def _resolve_params(strategy: str, params_json: dict | None) -> dict:
    """Merge user overrides with strategy defaults.

    Returns a plain dict with all required params for the strategy.
    """
    defaults = STRATEGY_DEFAULTS.get(strategy, {})
    if params_json:
        return {**defaults, **params_json}
    return dict(defaults)


def _generate_signals_for_strategy(df, strategy: str, params: dict):
    """Call the appropriate signal function for the given strategy."""
    if strategy == "EMA":
        from src.algo_trading.signal.signal import SignalParams, generate_signals
        signal_params = SignalParams(
            fast_period=int(params.get("fast_period", 10)),
            slow_period=int(params.get("slow_period", 50)),
            atr_period=int(params.get("atr_period", 14)),
            atr_multiplier=float(params.get("atr_multiplier", 1.0)),
            sl_atr_mult=float(params.get("sl_atr_mult", 1.5)),
            tp_atr_mult=float(params.get("tp_atr_mult", 3.0)),
            use_sma200_filter=bool(params.get("use_sma200_filter", True)),
            sma200_period=int(params.get("sma200_period", 200)),
        )
        return generate_signals(df, signal_params)
    elif strategy == "RSI":
        from src.algo_trading.signal.signal import RsiSignalParams, generate_rsi_signals
        signal_params = RsiSignalParams(
            rsi_period=int(params.get("rsi_period", 14)),
            rsi_threshold=float(params.get("rsi_threshold", 50.0)),
            trend_ema_period=int(params.get("trend_ema_period", 200)),
            atr_period=int(params.get("atr_period", 14)),
            sl_atr_mult=float(params.get("sl_atr_mult", 1.5)),
            tp_atr_mult=float(params.get("tp_atr_mult", 3.0)),
        )
        return generate_rsi_signals(df, signal_params)
    else:
        raise ValueError(f"Unknown strategy: {strategy!r}")


# ---------------------------------------------------------------------------
# Live bar handler — called by APScheduler every H1 bar close (minute=2)
# ---------------------------------------------------------------------------


async def _apply_break_even(session, symbol: str, mt5, params: dict) -> None:
    """Move SL to entry for any open position that has reached the BE trigger price."""
    from src.algo_trading.journal.journal import get_open_positions

    be_trigger_pct = float(params.get("be_trigger_pct", 0.0))
    if be_trigger_pct <= 0:
        return

    open_positions = await get_open_positions(session, symbol=symbol)
    if not open_positions:
        return

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.warning("BE check: could not get tick for %s", symbol)
        return

    for trade in open_positions:
        entry = float(trade.entry_price)
        sl = float(trade.sl_price)
        tp = float(trade.tp_price)
        direction = trade.direction

        # Skip if BE already activated (SL already at entry)
        if abs(sl - entry) < 1e-6:
            continue

        # Compute trigger price and check current bid/ask
        if direction == 1:  # long
            be_trigger = entry + be_trigger_pct * (tp - entry)
            triggered = tick.bid >= be_trigger
        else:  # short
            be_trigger = entry - be_trigger_pct * (entry - tp)
            triggered = tick.ask <= be_trigger

        if not triggered:
            continue

        # Modify SL to entry on MT5 (TRADE_ACTION_SLTP)
        mt5_positions = mt5.positions_get(ticket=trade.ticket)
        if not mt5_positions:
            continue
        pos = mt5_positions[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": trade.ticket,
            "sl": entry,
            "tp": pos.tp,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            trade.sl_price = entry
            logger.info(
                "Break-even activated: ticket=%d SL moved to entry=%.5f",
                trade.ticket, entry,
            )
        else:
            retcode = result.retcode if result else "N/A"
            logger.warning(
                "BE SL modification failed: ticket=%d retcode=%s",
                trade.ticket, retcode,
            )


async def _run_live_bar(config_id_str: str, symbol: str, strategy: str) -> None:
    """Execute one H1 bar of live trading logic for the given config.

    Order of operations:
    1. Verify MT5 connection.
    2. Sync closed positions (MT5 → DB reconciliation).
    2.5. Apply break-even to open positions that hit the trigger.
    3. Read account equity; update peak.
    4. Check drawdown circuit breaker.
    5. Check daily loss circuit breaker.
    6. Fetch 200 H1 bars and generate signals.
    7. Check for open position on this symbol (dedup guard).
    8. Calculate position size and place order.
    9. Log trade and send Telegram alert.
    """
    from configs.settings import get_settings
    from src.algo_trading.data_feed.data_feed import fetch_ohlcv
    from src.algo_trading.executor.executor import place_order, _require_mt5
    from src.algo_trading.journal.journal import (
        close_live_trade,
        get_open_positions,
        open_live_trade,
    )
    from src.algo_trading.notifications.telegram import (
        notify_circuit_breaker,
        notify_trade_closed,
        notify_trade_opened,
    )
    from src.algo_trading.risk.risk import (
        check_daily_limit,
        check_drawdown_circuit,
        position_size,
    )

    settings = get_settings()
    config_id = uuid.UUID(config_id_str)

    async with AsyncSessionLocal() as session:
        # Load config row
        config = await session.get(LiveTradingConfig, config_id)
        if config is None or not config.enabled:
            logger.warning("Config %s not found or disabled — skipping bar.", config_id_str)
            return

        config.status = "running"
        await session.flush()

        try:
            # 1. Verify MT5 connection
            _require_mt5(host=settings.MT5_HOST, port=settings.MT5_PORT)

            # Lazy import MT5 after _require_mt5 ensures it's connected
            try:
                import MetaTrader5 as mt5  # type: ignore[import]
            except ImportError:
                from mt5linux import MetaTrader5 as mt5  # type: ignore[import]

            # 2. Sync closed positions
            await _sync_closed_positions(
                session, symbol, mt5, notify_trade_closed
            )

            # Resolve params early — needed for break-even check below
            params = _resolve_params(config.strategy, config.params_json)

            # 2.5. Apply break-even to open positions that hit the trigger
            await _apply_break_even(session, symbol, mt5, params)

            # 3. Account equity
            account = mt5.account_info()
            if account is None:
                raise RuntimeError("Could not retrieve MT5 account info.")

            current_equity = float(account.equity)

            if config.session_start_equity is None:
                config.session_start_equity = current_equity

            prev_peak = _peak_equity.get(config_id_str, current_equity)
            if config.peak_equity is not None:
                prev_peak = max(prev_peak, float(config.peak_equity))
            peak = max(prev_peak, current_equity)
            _peak_equity[config_id_str] = peak
            config.peak_equity = peak

            session_start = float(config.session_start_equity)

            # 4. Drawdown circuit breaker
            if check_drawdown_circuit(peak, current_equity, settings.MAX_DRAWDOWN_PCT):
                logger.critical(
                    "DRAWDOWN CIRCUIT BREAKER for %s %s — halting.", symbol, strategy
                )
                config.status = "halted_drawdown"
                config.enabled = False
                await session.commit()
                _remove_scheduler_job(config_id_str)
                await notify_circuit_breaker(
                    reason=f"10% drawdown reached ({symbol} {strategy})",
                    equity=current_equity,
                    symbol=symbol,
                )
                return

            # 5. Daily loss circuit breaker
            if check_daily_limit(session_start, current_equity, settings.MAX_DAILY_LOSS_PCT):
                logger.warning(
                    "DAILY LOSS LIMIT for %s %s — skipping bar.", symbol, strategy
                )
                config.status = "halted_daily"
                await session.commit()
                await notify_circuit_breaker(
                    reason=f"3% daily loss limit reached ({symbol} {strategy})",
                    equity=current_equity,
                    symbol=symbol,
                )
                return

            # 6. Fetch data and generate signals
            try:
                import MetaTrader5 as _mt5_tf  # type: ignore[import]
                tf = _mt5_tf.TIMEFRAME_H1
            except ImportError:
                tf = 16385  # mt5linux numeric constant for TIMEFRAME_H1

            df = fetch_ohlcv(symbol, tf, count=200)
            df = _generate_signals_for_strategy(df, config.strategy, params)
            last = df.iloc[-1]
            signal = int(last["signal"])

            config.last_run_at = datetime.now(timezone.utc)
            config.last_signal = signal

            if signal == 0:
                config.status = "running"
                await session.commit()
                return

            # 7. Deduplication guard — one open position per symbol
            open_positions = await get_open_positions(session, symbol=symbol)
            if open_positions:
                logger.info(
                    "Open position already exists for %s — skipping signal.", symbol
                )
                config.status = "running"
                await session.commit()
                return

            # 8. Position sizing
            sl_price = float(last["sl_price"])
            tp_price = float(last["tp_price"])
            close_price = float(last["close"])

            pip_factor = 10.0 if symbol != "XAUUSD" else 1.0
            pip_value = 10.0 if symbol != "XAUUSD" else 1.0
            sl_pips = abs(close_price - sl_price) * pip_factor

            lots = position_size(
                account_equity=current_equity,
                stop_loss_pips=sl_pips,
                pip_value=pip_value,
                risk_pct=settings.RISK_PCT,
            )

            # 9. Place order
            result = place_order(
                symbol,
                signal,
                lots,
                sl_price,
                tp_price,
                comment=f"AlgoTrader-{strategy}",
            )

            trade_id = await open_live_trade(
                session,
                symbol=symbol,
                direction=signal,
                lots=lots,
                entry_price=result.entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
                ticket=result.ticket,
                account_equity_at_entry=current_equity,
                strategy=config.strategy,
            )
            config.status = "running"
            config.last_error = None
            await session.commit()

            logger.info(
                "Live order placed: symbol=%s dir=%d ticket=%d lots=%.2f id=%s",
                symbol,
                signal,
                result.ticket,
                lots,
                trade_id,
            )

            await notify_trade_opened(
                symbol=symbol,
                direction=signal,
                lots=lots,
                entry_price=result.entry_price,
                sl_price=sl_price,
                tp_price=tp_price,
                ticket=result.ticket,
            )

        except Exception as exc:
            logger.exception("Error in live bar for %s %s: %s", symbol, strategy, exc)
            config.status = "error"
            config.last_error = str(exc)[:500]
            await session.commit()


async def _sync_closed_positions(
    session,
    symbol: str,
    mt5,
    notify_trade_closed,
) -> None:
    """Reconcile DB open positions against live MT5 positions.

    For any position that is 'open' in the DB but no longer in MT5,
    fetch close details from MT5 history and mark the DB row as closed.
    """
    from src.algo_trading.journal.journal import close_live_trade, get_open_positions

    open_db = await get_open_positions(session, symbol=symbol)
    if not open_db:
        return

    mt5_positions = mt5.positions_get(symbol=symbol) or []
    mt5_tickets = {p.ticket for p in mt5_positions}

    for trade in open_db:
        if trade.ticket not in mt5_tickets:
            # Position was closed by MT5 (SL/TP hit) — find the close deal
            now = datetime.now(timezone.utc)
            from_dt = trade.entry_time
            deals = mt5.history_deals_get(from_dt, now, group=f"*{symbol}*") or []

            exit_price = 0.0
            pnl = 0.0
            exit_reason = "unknown"

            for deal in deals:
                if deal.position_id == trade.ticket and deal.entry == 1:  # ENTRY_OUT
                    exit_price = deal.price
                    pnl = deal.profit
                    if deal.reason == 3:  # DEAL_REASON_SL
                        exit_reason = "SL"
                    elif deal.reason == 4:  # DEAL_REASON_TP
                        exit_reason = "TP"
                    else:
                        exit_reason = "manual"
                    break

            try:
                await close_live_trade(
                    session,
                    ticket=trade.ticket,
                    exit_price=exit_price,
                    pnl=pnl,
                    exit_reason=exit_reason,
                )
                await session.flush()
                logger.info(
                    "Synced closed position: ticket=%d reason=%s pnl=%.2f",
                    trade.ticket,
                    exit_reason,
                    pnl,
                )
                await notify_trade_closed(
                    symbol=symbol,
                    direction=trade.direction,
                    pnl=pnl,
                    exit_reason=exit_reason,
                    exit_price=exit_price,
                    ticket=trade.ticket,
                )
            except Exception as exc:
                logger.warning("Failed to sync closed position ticket=%d: %s", trade.ticket, exc)


def _add_scheduler_job(config_id_str: str, symbol: str, strategy: str) -> None:
    scheduler.add_job(
        _run_live_bar,
        trigger=CronTrigger(minute=2),
        id=config_id_str,
        args=[config_id_str, symbol, strategy],
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("Scheduled live job for %s %s (id=%s)", symbol, strategy, config_id_str)


def _remove_scheduler_job(config_id_str: str) -> None:
    try:
        scheduler.remove_job(config_id_str)
        logger.info("Removed live job id=%s", config_id_str)
    except Exception:
        pass  # job may not exist


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------


@router.get("/configs", response_model=list[LiveConfigRead], summary="List live trading configs")
async def list_configs(db: DBSession) -> list[LiveTradingConfig]:
    result = await db.execute(
        select(LiveTradingConfig).order_by(LiveTradingConfig.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/configs",
    response_model=LiveConfigRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a live trading config",
)
async def create_config(body: LiveConfigCreate, db: DBSession) -> LiveTradingConfig:
    # Check uniqueness (one EMA and one RSI per symbol)
    existing = await db.execute(
        select(LiveTradingConfig).where(
            LiveTradingConfig.symbol == body.symbol,
            LiveTradingConfig.strategy == body.strategy,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Config for {body.symbol} {body.strategy} already exists.",
        )

    config = LiveTradingConfig(
        symbol=body.symbol,
        strategy=body.strategy,
        params_json=body.params_json,
        enabled=False,
        status="idle",
    )
    db.add(config)
    await db.flush()
    return config


@router.patch("/configs/{config_id}", response_model=LiveConfigRead, summary="Update config params")
async def update_config(
    config_id: uuid.UUID, body: LiveConfigUpdate, db: DBSession
) -> LiveTradingConfig:
    config = await db.get(LiveTradingConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found.")
    if config.enabled:
        raise HTTPException(
            status_code=400, detail="Disable the config before modifying it."
        )
    if body.params_json is not None:
        config.params_json = body.params_json
    await db.flush()
    return config


@router.delete(
    "/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a config",
)
async def delete_config(config_id: uuid.UUID, db: DBSession) -> None:
    config = await db.get(LiveTradingConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found.")
    _remove_scheduler_job(str(config_id))
    await db.delete(config)


# ---------------------------------------------------------------------------
# Enable / disable
# ---------------------------------------------------------------------------


@router.post(
    "/configs/{config_id}/enable",
    response_model=LiveConfigRead,
    summary="Enable live trading for this config",
)
async def enable_config(config_id: uuid.UUID, db: DBSession) -> LiveTradingConfig:
    config = await db.get(LiveTradingConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found.")
    if config.enabled:
        return config

    config.enabled = True
    config.status = "running"
    config.session_start_equity = None  # reset on new session
    config.last_error = None
    await db.flush()

    _add_scheduler_job(str(config_id), config.symbol, config.strategy)
    return config


@router.post(
    "/configs/{config_id}/disable",
    response_model=LiveConfigRead,
    summary="Disable live trading for this config",
)
async def disable_config(config_id: uuid.UUID, db: DBSession) -> LiveTradingConfig:
    config = await db.get(LiveTradingConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found.")

    config.enabled = False
    config.status = "idle"
    await db.flush()

    _remove_scheduler_job(str(config_id))
    return config


# ---------------------------------------------------------------------------
# Trade history endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[LiveTradeRead], summary="List live trades")
async def list_live_trades(
    db: DBSession,
    symbol: Optional[str] = Query(default=None),
    trade_status: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[LiveTrade]:
    from src.algo_trading.journal.journal import get_live_trades

    return await get_live_trades(
        db, symbol=symbol, status=trade_status, limit=limit, offset=offset
    )


@router.get("/open", response_model=list[LiveTradeRead], summary="Get open live positions")
async def get_open_live_positions(
    db: DBSession,
    symbol: Optional[str] = Query(default=None),
) -> list[LiveTrade]:
    from src.algo_trading.journal.journal import get_open_positions

    return await get_open_positions(db, symbol=symbol)


@router.get("/stats", response_model=LiveStatsRead, summary="Live trading aggregate stats")
async def get_live_stats(db: DBSession) -> LiveStatsRead:
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    # Aggregate counts
    count_result = await db.execute(
        select(
            func.count(LiveTrade.id).label("total"),
            func.count(LiveTrade.id)
            .filter(LiveTrade.status == "open")
            .label("open_count"),
            func.count(LiveTrade.id)
            .filter(LiveTrade.status == "closed")
            .label("closed_count"),
            func.count(LiveTrade.id)
            .filter(LiveTrade.status == "closed", LiveTrade.pnl > 0)
            .label("win_count"),
            func.count(LiveTrade.id)
            .filter(LiveTrade.status == "closed", LiveTrade.pnl <= 0)
            .label("loss_count"),
            func.coalesce(func.sum(LiveTrade.pnl).filter(LiveTrade.status == "closed"), 0).label(
                "total_pnl"
            ),
            func.coalesce(
                func.sum(LiveTrade.pnl).filter(
                    LiveTrade.status == "closed",
                    LiveTrade.exit_time >= today_start,
                ),
                0,
            ).label("today_pnl"),
        )
    )
    row = count_result.one()

    return LiveStatsRead(
        total_trades=row.total,
        open_count=row.open_count,
        closed_count=row.closed_count,
        win_count=row.win_count,
        loss_count=row.loss_count,
        total_pnl=float(row.total_pnl),
        today_pnl=float(row.today_pnl),
    )


@router.get("/{trade_id}", response_model=LiveTradeRead, summary="Get a single live trade")
async def get_live_trade(trade_id: uuid.UUID, db: DBSession) -> LiveTrade:
    trade = await db.get(LiveTrade, trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Live trade not found.")
    return trade
