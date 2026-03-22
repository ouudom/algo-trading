"""
main.py - AlgoTrader CLI entrypoint.

Supports two operating modes:
  backtest  - Load Parquet data, run the backtest engine, print metrics.
  paper     - Connect to MT5 in demo mode, stream live signals, log without executing.

Usage examples::

    python main.py --mode backtest --symbol XAUUSD --variation V1
    python main.py --mode backtest --symbol EURUSD --variation V3 --bars 10000
    python main.py --mode paper --symbol XAUUSD --variation V1
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure src/ is on PYTHONPATH when running the CLI from the project root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from configs.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("algo_trader.cli")

settings = get_settings()

# ---------------------------------------------------------------------------
# Variation catalogue — mirrors api/routers/strategies.py
# ---------------------------------------------------------------------------
from algo_trading.signal.signal import SignalParams

VARIATION_PARAMS: dict[str, SignalParams] = {
    "V1": SignalParams(fast_period=10, slow_period=50,  atr_period=14, atr_multiplier=1.0, sl_atr_mult=1.5, tp_atr_mult=3.0, sma200_period=200, use_sma200_filter=True),
    "V2": SignalParams(fast_period=8,  slow_period=30,  atr_period=14, atr_multiplier=0.8, sl_atr_mult=1.2, tp_atr_mult=2.5, sma200_period=200, use_sma200_filter=True),
    "V3": SignalParams(fast_period=5,  slow_period=20,  atr_period=10, atr_multiplier=0.5, sl_atr_mult=1.0, tp_atr_mult=2.0, sma200_period=200, use_sma200_filter=True),
    "V4": SignalParams(fast_period=20, slow_period=100, atr_period=20, atr_multiplier=1.2, sl_atr_mult=2.0, tp_atr_mult=4.0, sma200_period=200, use_sma200_filter=True),
    "V5": SignalParams(fast_period=3,  slow_period=15,  atr_period=7,  atr_multiplier=0.3, sl_atr_mult=0.8, tp_atr_mult=1.6, sma200_period=200, use_sma200_filter=False),
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="algo_trader",
        description="AlgoTrader CLI — MA Crossover + ATR strategy runner.",
    )
    parser.add_argument(
        "--mode",
        choices=["backtest", "paper"],
        required=True,
        help="Operating mode.",
    )
    parser.add_argument(
        "--symbol",
        default="XAUUSD",
        help="Instrument symbol (default: XAUUSD).",
    )
    parser.add_argument(
        "--variation",
        choices=list(VARIATION_PARAMS),
        default="V1",
        help="Strategy variation V1–V5 (default: V1).",
    )
    parser.add_argument(
        "--bars",
        type=int,
        default=5000,
        help="Number of bars to load/fetch (default: 5000).",
    )
    parser.add_argument(
        "--timeframe",
        default="H1",
        help="Bar timeframe string (default: H1). Used as target timeframe when --csv is given.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        metavar="FILE",
        help=(
            "Path to a Dukascopy or HistData CSV file. "
            "When provided, skips Parquet and loads directly from this file. "
            "Use --timeframe to resample (e.g. M1 source → H1 backtest)."
        ),
    )
    parser.add_argument(
        "--initial-equity",
        type=float,
        default=10_000.0,
        dest="initial_equity",
        help="Starting equity for backtest (default: 10000).",
    )
    return parser


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------


def run_backtest_mode(args: argparse.Namespace) -> None:
    """Load data and run a full backtest, printing results to stdout."""
    from algo_trading.data_feed import load_parquet
    from algo_trading.data_feed.data_feed import load_csv, resample_ohlcv, detect_timeframe_from_df
    from algo_trading.backtest import run_backtest, BacktestResult
    from algo_trading.backtest.backtest import BacktestParams
    from algo_trading.analytics import compute_metrics

    logger.info(
        "Backtest mode: symbol=%s variation=%s timeframe=%s csv=%s",
        args.symbol,
        args.variation,
        args.timeframe,
        args.csv or "(parquet)",
    )

    if args.csv:
        # Load directly from CSV file (Dukascopy or HistData format)
        try:
            df = load_csv(args.csv, args.symbol)
        except Exception as exc:
            logger.error("Failed to load CSV %s: %s", args.csv, exc)
            sys.exit(1)

        # Resample if the CSV's native timeframe differs from --timeframe
        native_tf = detect_timeframe_from_df(df)
        if args.timeframe != native_tf:
            logger.info(
                "Resampling %s → %s (source has %d bars)",
                native_tf,
                args.timeframe,
                len(df),
            )
            try:
                df = resample_ohlcv(df, args.timeframe)
            except ValueError as exc:
                logger.error("Resample failed: %s", exc)
                sys.exit(1)
    else:
        try:
            df = load_parquet(
                symbol=args.symbol,
                timeframe=args.timeframe,
                base_dir=settings.PARQUET_DIR,
            )
        except FileNotFoundError as exc:
            logger.error("%s", exc)
            logger.error(
                "Hint: provide a CSV with --csv, or fetch Parquet data first:\n"
                "  from algo_trading.data_feed import fetch_ohlcv, save_parquet\n"
                "  df = fetch_ohlcv('%s', mt5.TIMEFRAME_H1, bars=%d)\n"
                "  save_parquet(df, '%s', 'H1')",
                args.symbol,
                args.bars,
                args.symbol,
            )
            sys.exit(1)

    # XAUUSD: 1 pip = $0.01 (pip_factor=100), pip_value = $1/lot/pip
    # Forex 4-decimal pairs (EURUSD etc.): pip_factor=10_000, pip_value=$10
    if args.symbol.upper() == "XAUUSD":
        pip_value, pip_factor = 1.0, 100
    else:
        pip_value, pip_factor = 10.0, 10_000

    params = BacktestParams(
        signal_params=VARIATION_PARAMS[args.variation],
        initial_equity=args.initial_equity,
        variation=args.variation,
        pip_value=pip_value,
        pip_factor=pip_factor,
        timeframe=args.timeframe,
    )

    result: BacktestResult = run_backtest(df, params)
    metrics = compute_metrics(result.trades, initial_equity=args.initial_equity)

    _print_results(args, metrics)


def run_paper_mode(args: argparse.Namespace) -> None:
    """Connect to MT5 in demo mode and stream live signals without placing real orders."""
    logger.info(
        "Paper trading mode: symbol=%s variation=%s",
        args.symbol,
        args.variation,
    )

    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError:
        logger.error("MetaTrader5 package is not installed (Windows-only).")
        sys.exit(1)

    if not mt5.initialize(
        login=settings.MT5_LOGIN,
        password=settings.MT5_PASSWORD,
        server=settings.MT5_SERVER,
    ):
        logger.error("Failed to connect to MT5 terminal: %s", mt5.last_error())
        sys.exit(1)

    logger.info("MT5 connected. Entering live signal loop. Press Ctrl+C to stop.")

    from algo_trading.signal import generate_signals
    from algo_trading.data_feed import fetch_ohlcv
    import time

    _TF_MAP = {"H1": mt5.TIMEFRAME_H1, "M15": mt5.TIMEFRAME_M15}
    tf = _TF_MAP.get(args.timeframe, mt5.TIMEFRAME_H1)

    try:
        while True:
            df = fetch_ohlcv(args.symbol, tf, bars=200)
            sig_df = generate_signals(df, VARIATION_PARAMS[args.variation])
            last = sig_df.iloc[-1]
            sig = int(last["signal"])
            if sig != 0:
                direction = "LONG" if sig == 1 else "SHORT"
                logger.info(
                    "[PAPER SIGNAL] %s %s | close=%.5f sl=%.5f tp=%.5f atr=%.5f",
                    args.symbol,
                    direction,
                    last["close"],
                    last["sl_price"],
                    last["tp_price"],
                    last["atr"],
                )
            else:
                logger.debug("No signal on latest bar.")
            # Wait for next bar close (simplified: poll every 60 s)
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Paper trading stopped by user.")
    finally:
        mt5.shutdown()


def _print_results(args: argparse.Namespace, metrics: dict) -> None:
    """Pretty-print backtest metrics to stdout."""
    print("\n" + "=" * 60)
    print(f"  Backtest Results — {args.symbol} {args.variation}")
    print("=" * 60)
    for key, value in metrics.items():
        label = key.replace("_", " ").title()
        print(f"  {label:<30} {value}")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "backtest":
        run_backtest_mode(args)
    elif args.mode == "paper":
        run_paper_mode(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
