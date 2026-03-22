"""
routers/backtests.py - Backtest run endpoints.

Routes
------
GET  /backtests/              - Paginated list of backtest runs.
GET  /backtests/{id}          - Single backtest run with metrics.
GET  /backtests/{id}/equity   - Equity curve data for chart rendering.
POST /backtests/run           - Submit an async backtest job (202).
GET  /backtests/{id}/status   - Poll the status of a submitted job.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import select

from algo_trading.backtest.backtest import BacktestParams, run_backtest
from algo_trading.data_feed.data_feed import load_csv, resample_ohlcv
from algo_trading.indicators.indicators import ema, rsi as compute_rsi
from algo_trading.signal.signal import RsiSignalParams, SignalParams
from api.db import AsyncSessionLocal
from api.deps import DBSession
from api.models.backtest_run import BacktestMetric, BacktestRun
from api.models.trade import BacktestTrade
from api.schemas.backtest import (
    BacktestEquityCurveRead,
    BacktestRunRead,
    BacktestRunRequest,
    BacktestStatusResponse,
    BacktestSubmitResponse,
    EquityPoint,
)
from api.schemas.trade import TradeRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get(
    "/",
    response_model=list[BacktestRunRead],
    summary="List backtest runs",
    description="Return a paginated list of backtest runs ordered by creation time descending.",
)
async def list_backtests(
    db: DBSession,
    symbol: str | None = Query(default=None, description="Filter by symbol"),
    variation: str | None = Query(default=None, description="Filter by strategy variation"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[BacktestRun]:
    """Return backtest run summaries, newest first."""
    stmt = (
        select(BacktestRun)
        .order_by(BacktestRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if symbol is not None:
        stmt = stmt.where(BacktestRun.symbol == symbol.upper())
    if variation is not None:
        stmt = stmt.where(BacktestRun.variation == variation)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/{run_id}",
    response_model=BacktestRunRead,
    summary="Get backtest run",
    description="Return a single backtest run including all associated metric rows.",
)
async def get_backtest(run_id: uuid.UUID, db: DBSession) -> BacktestRun:
    """Return a single backtest run or raise 404."""
    stmt = select(BacktestRun).where(BacktestRun.id == run_id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BacktestRun {run_id} not found.",
        )
    return run


@router.get(
    "/{run_id}/equity",
    response_model=BacktestEquityCurveRead,
    summary="Get equity curve",
    description=(
        "Return the equity curve stored for a backtest run. "
        "The curve is stored as a JSON array in the ``equity_curve`` BacktestMetric row."
    ),
)
async def get_equity_curve(run_id: uuid.UUID, db: DBSession) -> BacktestEquityCurveRead:
    """Return the equity curve for a given backtest run."""
    # Verify the run exists
    run_stmt = select(BacktestRun).where(BacktestRun.id == run_id)
    run_result = await db.execute(run_stmt)
    run = run_result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BacktestRun {run_id} not found.",
        )

    # Fetch the equity_curve metric row
    metric_stmt = select(BacktestMetric).where(
        BacktestMetric.run_id == run_id,
        BacktestMetric.metric_key == "equity_curve",
    )
    metric_result = await db.execute(metric_stmt)
    metric = metric_result.scalar_one_or_none()

    if metric is None or metric.value_json is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No equity curve stored for BacktestRun {run_id}.",
        )

    # Expect value_json to be a list of {"timestamp": "...", "equity": float}
    points = [
        EquityPoint(timestamp=p["timestamp"], equity=p["equity"])
        for p in metric.value_json
    ]

    return BacktestEquityCurveRead(
        run_id=run_id,
        initial_equity=float(run.initial_equity),
        points=points,
    )


@router.get(
    "/{run_id}/candles",
    response_model=list[dict],
    summary="Get OHLCV candles with EMA lines",
    description=(
        "Return the OHLCV bars and EMA fast/slow values for a backtest run. "
        "Loads the original CSV file referenced in params_json and resamples "
        "to the run's timeframe. Times are Unix seconds (UTC)."
    ),
)
async def get_candles(run_id: uuid.UUID, db: DBSession) -> list[dict]:
    """Load OHLCV data + EMAs for the chart overlay."""
    stmt = select(BacktestRun).where(BacktestRun.id == run_id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BacktestRun {run_id} not found.",
        )

    params = run.params_json or {}
    file_id = params.get("file_id")
    if not file_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="BacktestRun has no associated data file (file_id missing from params_json).",
        )

    csv_path = Path("data/raw") / f"{file_id}.csv"
    if not csv_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source CSV file not found: {file_id}. It may have been deleted.",
        )

    try:
        df = await _load_and_filter(csv_path, run)
    except Exception as exc:
        logger.exception("Failed to load OHLCV for run %s: %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load OHLCV data: {exc}",
        ) from exc

    strategy = params.get("strategy", "ma_crossover")
    bars: list[dict] = []

    if strategy == "rsi_momentum":
        rsi_period = int(params.get("rsi_period") or 14)
        trend_ema_period = int(params.get("trend_ema_period") or 200)
        trend_ema_series = ema(df["close"], trend_ema_period)
        rsi_series = compute_rsi(df["close"], rsi_period)

        for ts, row in df.iterrows():
            te = trend_ema_series.loc[ts]
            rv = rsi_series.loc[ts]
            bars.append({
                "time":      int(ts.timestamp()),
                "open":      float(row["open"]),
                "high":      float(row["high"]),
                "low":       float(row["low"]),
                "close":     float(row["close"]),
                "trend_ema": None if (isinstance(te, float) and math.isnan(te)) else float(te),
                "rsi":       None if (isinstance(rv, float) and math.isnan(rv)) else float(rv),
            })
    else:
        ema_fast_period = int(params.get("ema_fast", 20))
        ema_slow_period = int(params.get("ema_slow", 50))
        ema_fast_series = ema(df["close"], ema_fast_period)
        ema_slow_series = ema(df["close"], ema_slow_period)

        for ts, row in df.iterrows():
            ef = ema_fast_series.loc[ts]
            es = ema_slow_series.loc[ts]
            bars.append({
                "time":     int(ts.timestamp()),
                "open":     float(row["open"]),
                "high":     float(row["high"]),
                "low":      float(row["low"]),
                "close":    float(row["close"]),
                "ema_fast": None if (isinstance(ef, float) and math.isnan(ef)) else float(ef),
                "ema_slow": None if (isinstance(es, float) and math.isnan(es)) else float(es),
            })

    return bars


async def _load_and_filter(csv_path: Path, run: BacktestRun) -> pd.DataFrame:
    """Load CSV, resample to run timeframe, filter to run date range."""
    import asyncio

    loop = asyncio.get_event_loop()
    params = run.params_json or {}

    def _blocking() -> pd.DataFrame:
        df = load_csv(str(csv_path), run.symbol)

        target_tf = run.timeframe or params.get("timeframe")
        if target_tf:
            meta_path = csv_path.with_suffix("").with_suffix(".meta.json")
            native_tf = "H1"
            if meta_path.exists():
                with open(meta_path) as f:
                    native_tf = json.load(f).get("timeframe", "H1")
            if target_tf != native_tf:
                df = resample_ohlcv(df, target_tf)

        if run.start_date is not None:
            ts_start = pd.Timestamp(run.start_date)
            if ts_start.tzinfo is None:
                ts_start = ts_start.tz_localize("UTC")
            else:
                ts_start = ts_start.tz_convert("UTC")
            df = df[df.index >= ts_start]
        if run.end_date is not None:
            ts_end = pd.Timestamp(run.end_date)
            if ts_end.tzinfo is None:
                ts_end = ts_end.tz_localize("UTC")
            else:
                ts_end = ts_end.tz_convert("UTC")
            df = df[df.index <= ts_end]

        return df

    return await loop.run_in_executor(None, _blocking)


@router.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=BacktestSubmitResponse,
    summary="Submit async backtest job",
    description=(
        "Submit a backtest run request. The job is queued as a background task "
        "and the run_id can be used to poll status via GET /backtests/{id}/status."
    ),
)
async def run_backtest_endpoint(
    request: BacktestRunRequest,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> BacktestSubmitResponse:
    """Validate the file_id, create a pending BacktestRun row, and enqueue the job."""
    csv_path = Path("data/raw") / f"{request.file_id}.csv"
    if not csv_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data file not found: {request.file_id}. Upload it first via POST /data/upload.",
        )

    # Read the detected timeframe from the sidecar metadata written at upload time
    meta_path = Path("data/raw") / f"{request.file_id}.meta.json"
    file_timeframe = "H1"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            file_timeframe = meta.get("timeframe", "H1")
        except Exception:
            pass

    # Use requested target timeframe if provided, otherwise use file's native timeframe
    target_timeframe = request.timeframe or file_timeframe

    run = BacktestRun(
        symbol=request.symbol.upper(),
        variation=request.variation,
        timeframe=target_timeframe,
        initial_equity=request.initial_equity,
        total_trades=0,
        status="pending",
        params_json=request.model_dump(),
    )
    db.add(run)
    await db.commit()  # commit so the background task's new session can see the row
    await db.refresh(run)

    background_tasks.add_task(_run_backtest_task, run.id, request)

    return BacktestSubmitResponse(run_id=str(run.id), status="pending")


@router.delete(
    "/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete backtest run",
    description=(
        "Permanently delete a backtest run and all associated trades and metrics. "
        "This action cannot be undone."
    ),
)
async def delete_backtest(run_id: uuid.UUID, db: DBSession) -> None:
    """Delete a backtest run (cascades to trades and metrics via FK constraints)."""
    stmt = select(BacktestRun).where(BacktestRun.id == run_id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BacktestRun {run_id} not found.",
        )

    await db.delete(run)
    await db.commit()


@router.get(
    "/{run_id}/trades",
    response_model=list[TradeRead],
    summary="List trades for a backtest run",
    description="Return all simulated trades belonging to a specific backtest run, ordered by entry time.",
)
async def list_backtest_trades(
    run_id: uuid.UUID,
    db: DBSession,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[BacktestTrade]:
    """Return trades for a given backtest run or raise 404 if the run does not exist."""
    run_stmt = select(BacktestRun).where(BacktestRun.id == run_id)
    run_result = await db.execute(run_stmt)
    if run_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BacktestRun {run_id} not found.",
        )

    trade_stmt = (
        select(BacktestTrade)
        .where(BacktestTrade.backtest_run_id == run_id)
        .order_by(BacktestTrade.entry_time.asc())
        .offset(offset)
        .limit(limit)
    )
    trade_result = await db.execute(trade_stmt)
    return list(trade_result.scalars().all())


@router.get(
    "/{run_id}/status",
    response_model=BacktestStatusResponse,
    summary="Poll backtest job status",
    description="Return the current status and progress of a submitted backtest job.",
)
async def get_backtest_status(
    run_id: uuid.UUID,
    db: DBSession,
) -> BacktestStatusResponse:
    """Return the status of a submitted backtest job."""
    stmt = select(BacktestRun).where(BacktestRun.id == run_id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BacktestRun {run_id} not found.",
        )

    progress_map = {"pending": 0.0, "running": 50.0, "completed": 100.0, "failed": 100.0}
    progress_pct = progress_map.get(run.status, 0.0)

    error: str | None = None
    if run.status == "failed" and run.params_json:
        error = run.params_json.get("error")

    return BacktestStatusResponse(
        run_id=str(run.id),
        status=run.status,
        progress_pct=progress_pct,
        error=error,
    )


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------


async def _run_backtest_task(run_id: uuid.UUID, request: BacktestRunRequest) -> None:
    """Execute a backtest in the background and persist results to the database."""
    async with AsyncSessionLocal() as session:
        try:
            # --- Mark as running --------------------------------------------
            stmt = select(BacktestRun).where(BacktestRun.id == run_id)
            result = await session.execute(stmt)
            run = result.scalar_one()
            run.status = "running"
            await session.commit()

            # --- Load and filter data ---------------------------------------
            csv_path = f"data/raw/{request.file_id}.csv"
            meta_path_bg = Path(f"data/raw/{request.file_id}.meta.json")
            bg_timeframe = "H1"
            if meta_path_bg.exists():
                try:
                    meta_bg = json.loads(meta_path_bg.read_text(encoding="utf-8"))
                    bg_timeframe = meta_bg.get("timeframe", "H1")
                except Exception:
                    pass
            df = load_csv(csv_path, request.symbol)

            # Resample to target timeframe if specified and different from native
            actual_timeframe = bg_timeframe
            if request.timeframe and request.timeframe != bg_timeframe:
                df = resample_ohlcv(df, request.timeframe)
                actual_timeframe = request.timeframe

            if request.start_date is not None:
                df = df[df.index >= pd.Timestamp(request.start_date, tz="UTC")]
            if request.end_date is not None:
                # A date-only string like "2026-03-20" resolves to midnight,
                # which would drop all bars after 00:00 on that day.
                # Append end-of-day so the full day is included.
                end_ts_str = request.end_date
                if len(end_ts_str) == 10:
                    end_ts_str += "T23:59:59"
                df = df[df.index <= pd.Timestamp(end_ts_str, tz="UTC")]

            # --- Build params and run backtest (strategy dispatch) -----------
            if request.strategy == "rsi_momentum":
                signal_params = RsiSignalParams(
                    rsi_period=request.rsi_period if request.rsi_period is not None else 14,
                    rsi_threshold=request.rsi_threshold if request.rsi_threshold is not None else 50.0,
                    trend_ema_period=request.trend_ema_period if request.trend_ema_period is not None else 200,
                    atr_period=request.atr_period,
                    sl_atr_mult=request.sl_multiplier,
                    tp_atr_mult=request.tp_multiplier,
                )
                strategy_label = "RSI_TREND"
            else:
                signal_params = SignalParams(
                    fast_period=request.ema_fast,
                    slow_period=request.ema_slow,
                    atr_period=request.atr_period,
                    sl_atr_mult=request.sl_multiplier,
                    tp_atr_mult=request.tp_multiplier,
                    sma200_period=request.sma200_period,
                    use_sma200_filter=request.use_sma200_filter,
                )
                strategy_label = "MA_ATR"
            # XAUUSD: 1 pip = $0.01 (pip_factor=100), pip_value = $1/lot/pip
            # Forex 4-decimal pairs (EURUSD etc.): pip_factor=10_000, pip_value=$10
            symbol_upper = request.symbol.upper()
            if symbol_upper == "XAUUSD":
                pip_value, pip_factor = 1.0, 100
            else:
                pip_value, pip_factor = 10.0, 10_000

            params = BacktestParams(
                signal_params=signal_params,
                initial_equity=request.initial_equity,
                variation=request.variation,
                pip_value=pip_value,
                pip_factor=pip_factor,
                timeframe=actual_timeframe,
                be_trigger_pct=request.be_trigger_pct,
            )
            bt_result = run_backtest(df, params)

            # --- Persist results --------------------------------------------
            # Re-fetch run inside this session to update it
            result2 = await session.execute(select(BacktestRun).where(BacktestRun.id == run_id))
            run = result2.scalar_one()

            def _safe(v) -> float | None:
                """Convert to Python float; return None for inf/nan (DB can't store them)."""
                try:
                    f = float(v)
                    return None if (math.isinf(f) or math.isnan(f)) else f
                except (TypeError, ValueError):
                    return None

            run.final_equity = _safe(bt_result.equity_curve.iloc[-1] if len(bt_result.equity_curve) > 0 else request.initial_equity)
            run.total_trades = bt_result.total_trades
            run.win_rate = _safe(bt_result.win_rate)
            run.profit_factor = _safe(bt_result.profit_factor)
            run.total_return_pct = _safe(bt_result.total_return_pct)
            run.sharpe_ratio = _safe(bt_result.sharpe_ratio)
            run.max_drawdown_pct = _safe(bt_result.max_drawdown_pct)
            run.start_date = df.index[0].to_pydatetime() if len(df) > 0 else None
            run.end_date = df.index[-1].to_pydatetime() if len(df) > 0 else None
            run.timeframe = actual_timeframe
            run.status = "completed"

            # --- Persist equity curve as a BacktestMetric row ---------------
            equity_data = [
                {"timestamp": t.isoformat(), "equity": float(v)}
                for t, v in bt_result.equity_curve.items()
            ]
            metric = BacktestMetric(
                run_id=run.id,
                metric_key="equity_curve",
                value_json=equity_data,
            )
            session.add(metric)

            # --- Persist individual simulated trades -------------------------
            if not bt_result.trades.empty:
                trade_rows = [
                    BacktestTrade(
                        backtest_run_id=run.id,
                        symbol=request.symbol.upper(),
                        direction=int(row["direction"]),
                        lots=float(row["lots"]),
                        entry_price=float(row["entry_price"]),
                        sl_price=float(row["sl_price"]),
                        tp_price=float(row["tp_price"]),
                        entry_time=pd.Timestamp(row["entry_time"]).to_pydatetime(),
                        exit_price=float(row["exit_price"]),
                        exit_time=pd.Timestamp(row["exit_time"]).to_pydatetime(),
                        exit_reason=str(row["exit_reason"]),
                        pnl=float(row["pnl"]),
                        strategy=strategy_label,
                        variation=request.variation,
                    )
                    for _, row in bt_result.trades.iterrows()
                ]
                session.add_all(trade_rows)

            await session.commit()

            logger.info(
                "Backtest task completed: run_id=%s trades=%d return=%.2f%%",
                run_id,
                bt_result.total_trades,
                bt_result.total_return_pct,
            )

        except Exception as exc:
            logger.exception("Backtest task failed for run_id=%s: %s", run_id, exc)
            try:
                await session.rollback()
                result_err = await session.execute(select(BacktestRun).where(BacktestRun.id == run_id))
                run_err = result_err.scalar_one_or_none()
                if run_err is not None:
                    run_err.status = "failed"
                    params_json = run_err.params_json or {}
                    params_json["error"] = str(exc)
                    run_err.params_json = params_json
                    await session.commit()
            except Exception:
                logger.exception("Failed to persist error state for run_id=%s", run_id)
