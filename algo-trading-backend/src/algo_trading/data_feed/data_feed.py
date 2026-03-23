"""
data_feed.py - MetaTrader 5 OHLCV data ingestion with Parquet-based persistence.

Responsibilities:
    - Connect to a running MT5 terminal and pull OHLCV bars for a given symbol/timeframe.
    - Persist raw and processed data to Parquet files for fast columnar reads.
    - Load previously cached Parquet data so live and backtest pipelines share the same source.
    - Parse Dukascopy historical CSV exports for backtesting on non-Windows systems.

Typical usage::

    df = fetch_ohlcv("XAUUSD", mt5.TIMEFRAME_H1, bars=5000)
    save_parquet(df, symbol="XAUUSD", timeframe="H1", base_dir="data/parquet")
    df = load_parquet(symbol="XAUUSD", timeframe="H1", base_dir="data/parquet")

    # macOS / non-Windows: use Dukascopy CSV instead of MT5
    df = load_dukascopy_csv("data/raw/XAUUSD_H1.csv", symbol="XAUUSD", timeframe="H1")
    save_parquet(df, symbol="XAUUSD", timeframe="H1", base_dir="data/parquet")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# MetaTrader5 is only available on Windows with MT5 installed.
# We import lazily so the rest of the codebase can be exercised on any OS.
try:
    import MetaTrader5 as mt5  # type: ignore
    _MT5_AVAILABLE = True
except ImportError:  # pragma: no cover
    mt5 = None  # type: ignore
    _MT5_AVAILABLE = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_ohlcv(
    symbol: str,
    timeframe: int,
    bars: int = 5000,
    *,
    mt5_login: Optional[int] = None,
    mt5_password: Optional[str] = None,
    mt5_server: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch OHLCV bars from a running MetaTrader 5 terminal.

    Connects to MT5 (or reuses an existing connection), copies ``bars`` worth
    of historical data for ``symbol`` at ``timeframe`` resolution, and returns
    a tidy DataFrame indexed by UTC datetime.

    Parameters
    ----------
    symbol:
        MT5 symbol name, e.g. ``"XAUUSD"`` or ``"EURUSD"``.
    timeframe:
        MT5 timeframe constant, e.g. ``mt5.TIMEFRAME_H1``.
    bars:
        Number of completed bars to retrieve (most recent).
    mt5_login:
        MT5 account number. Reads from ``MT5_LOGIN`` env var when *None*.
    mt5_password:
        MT5 password. Reads from ``MT5_PASSWORD`` env var when *None*.
    mt5_server:
        MT5 broker server name. Reads from ``MT5_SERVER`` env var when *None*.

    Returns
    -------
    pd.DataFrame
        Columns: ``open``, ``high``, ``low``, ``close``, ``volume``.
        Index: ``time`` (``DatetimeTZDtype[UTC]``).

    Raises
    ------
    RuntimeError
        If MetaTrader5 package is not installed or connection fails.
    ValueError
        If MT5 returns no data for the requested symbol/timeframe.
    """
    if not _MT5_AVAILABLE:
        raise RuntimeError(
            "MetaTrader5 package is not installed. "
            "Install it with: pip install MetaTrader5  "
            "(Windows-only, requires MT5 terminal to be running)"
        )

    import os

    login = mt5_login or int(os.environ.get("MT5_LOGIN", "0"))
    password = mt5_password or os.environ.get("MT5_PASSWORD", "")
    server = mt5_server or os.environ.get("MT5_SERVER", "")

    logger.info("Initialising MT5 connection for symbol=%s timeframe=%s", symbol, timeframe)

    if not mt5.initialize(login=login, password=password, server=server):
        error = mt5.last_error()
        raise RuntimeError(f"MT5 initialisation failed: {error}")

    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    finally:
        mt5.shutdown()

    if rates is None or len(rates) == 0:
        raise ValueError(
            f"MT5 returned no data for symbol={symbol!r} timeframe={timeframe}. "
            "Check that the symbol is available in Market Watch."
        )

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time")
    df = df[["open", "high", "low", "close", "tick_volume"]].rename(
        columns={"tick_volume": "volume"}
    )
    df = df.sort_index()

    logger.info("Fetched %d bars for %s", len(df), symbol)
    return df


def save_parquet(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    base_dir: str | Path = "data/parquet",
) -> Path:
    """Persist an OHLCV DataFrame to a Parquet file.

    Files are stored at ``{base_dir}/{symbol}_{timeframe}.parquet``.

    Parameters
    ----------
    df:
        DataFrame produced by :func:`fetch_ohlcv`.
    symbol:
        Symbol name used as part of the filename, e.g. ``"XAUUSD"``.
    timeframe:
        Human-readable timeframe string, e.g. ``"H1"``.
    base_dir:
        Root directory for Parquet files. Created if it does not exist.

    Returns
    -------
    Path
        Absolute path of the written Parquet file.

    Raises
    ------
    ValueError
        If ``df`` is empty or missing required OHLCV columns.
    """
    required_columns = {"open", "high", "low", "close", "volume"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame is missing required columns: {missing}")

    if df.empty:
        raise ValueError("Cannot save an empty DataFrame to Parquet.")

    output_dir = Path(base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{symbol}_{timeframe}.parquet"
    path = output_dir / filename

    df.to_parquet(path, engine="pyarrow", compression="snappy", index=True)
    logger.info("Saved %d rows to %s", len(df), path)
    return path.resolve()


def load_parquet(
    symbol: str,
    timeframe: str,
    base_dir: str | Path = "data/parquet",
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Load a previously saved OHLCV Parquet file.

    Parameters
    ----------
    symbol:
        Symbol name used in the filename, e.g. ``"XAUUSD"``.
    timeframe:
        Timeframe string, e.g. ``"H1"``.
    base_dir:
        Root directory where Parquet files live.
    start:
        Optional ISO-8601 string to filter rows from this datetime (inclusive).
    end:
        Optional ISO-8601 string to filter rows up to this datetime (inclusive).

    Returns
    -------
    pd.DataFrame
        OHLCV DataFrame with a UTC datetime index, sorted ascending.

    Raises
    ------
    FileNotFoundError
        If the expected Parquet file does not exist.
    """
    path = Path(base_dir) / f"{symbol}_{timeframe}.parquet"

    if not path.exists():
        raise FileNotFoundError(
            f"Parquet file not found: {path}. "
            f"Run fetch_ohlcv() and save_parquet() first."
        )

    df = pd.read_parquet(path, engine="pyarrow")
    df = df.sort_index()

    if start is not None:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]

    logger.info("Loaded %d rows from %s", len(df), path)
    return df


def connect_mt5(
    login: int,
    password: str,
    server: str,
    timeout: int = 60_000,
) -> None:
    """Establish a connection to the MetaTrader 5 terminal.

    Call this once before using :func:`fetch_ohlcv` or placing orders when
    you want explicit control over the connection lifecycle. On non-Windows
    platforms where the MetaTrader5 package is unavailable, raises immediately.

    Parameters
    ----------
    login:
        MT5 account number.
    password:
        MT5 account password.
    server:
        MT5 broker server name, e.g. ``"XMGlobal-MT5"``.
    timeout:
        Connection timeout in milliseconds. Default 60 000.

    Raises
    ------
    RuntimeError
        If MT5 is not available or the connection attempt fails.
    """
    if not _MT5_AVAILABLE:
        raise RuntimeError(
            "MetaTrader5 package is not installed. "
            "Windows-only: requires MT5 terminal to be running."
        )
    if not mt5.initialize(login=login, password=password, server=server, timeout=timeout):
        error = mt5.last_error()
        raise RuntimeError(f"MT5 initialisation failed: {error}")
    logger.info("MT5 connected: login=%d server=%s", login, server)


def load_dukascopy_csv(
    filepath: str | Path,
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    """Parse a Dukascopy historical CSV export into a standard OHLCV DataFrame.

    Supports two Dukascopy export formats:

    **JForex (old):**::

        Gmt time,Open,High,Low,Close,Volume
        01.01.2021 00:00:00.000,1896.85,1898.75,1896.56,1897.56,34.67

    **Web export (new):**::

        UTC,Open,High,Low,Close,Volume
        01.03.2026 23:00:00.000 UTC,5372.198,5392.995,5296.668,5386.545,3.170581

    The returned DataFrame has the same shape and index convention as
    :func:`fetch_ohlcv`, so the two sources are interchangeable in the
    backtest pipeline.

    Parameters
    ----------
    filepath:
        Path to the ``.csv`` file downloaded from Dukascopy JForex.
    symbol:
        Symbol name used for logging only, e.g. ``"XAUUSD"``.
    timeframe:
        Timeframe string used for logging only, e.g. ``"H1"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``open``, ``high``, ``low``, ``close``, ``volume``.
        Index: ``time`` (``DatetimeTZDtype[UTC]``), sorted ascending.

    Raises
    ------
    FileNotFoundError
        If the file does not exist at ``filepath``.
    ValueError
        If required columns are missing or the DataFrame is empty after parsing.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Dukascopy CSV not found: {path}")

    # Detect which column name Dukascopy used (JForex: "Gmt time", web: "UTC")
    header_df = pd.read_csv(path, nrows=0, encoding="utf-8-sig")
    _TIME_COLUMN_CANDIDATES = ["Gmt time", "UTC"]
    time_col = next(
        (c for c in _TIME_COLUMN_CANDIDATES if c in header_df.columns),
        None,
    )
    if time_col is None:
        raise ValueError(
            f"Dukascopy CSV has no recognised time column. "
            f"Expected one of {_TIME_COLUMN_CANDIDATES}. Found: {list(header_df.columns)}"
        )

    df = pd.read_csv(path, encoding="utf-8-sig")

    # Strip trailing " UTC" suffix present in newer Dukascopy web exports
    df[time_col] = df[time_col].str.replace(r"\s+UTC$", "", regex=True)
    df[time_col] = pd.to_datetime(df[time_col], format="%d.%m.%Y %H:%M:%S.%f")
    df = df.set_index(time_col)

    if df.empty:
        raise ValueError(f"Dukascopy CSV is empty: {path}")

    # Normalise column names to lowercase to match internal convention
    df.columns = df.columns.str.lower()

    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Dukascopy CSV missing expected columns: {missing}. "
            f"Found: {list(df.columns)}"
        )

    df = df[["open", "high", "low", "close", "volume"]]

    # Ensure UTC timezone
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    df.index.name = "time"
    df = df.sort_index()

    logger.info(
        "Loaded %d bars from Dukascopy CSV: %s %s (%s to %s)",
        len(df),
        symbol,
        timeframe,
        df.index[0],
        df.index[-1],
    )
    return df


_TF_TO_PANDAS: dict[str, str] = {
    "M1":  "1min",
    "M5":  "5min",
    "M15": "15min",
    "M30": "30min",
    "M45": "45min",
    "H1":  "1h",
    "H2":  "2h",
    "H4":  "4h",
    "D1":  "1D",
    "W1":  "1W",
}


def load_histdata_csv(
    filepath: str | Path,
    symbol: str,
) -> pd.DataFrame:
    """Parse a HistData.com MetaTrader CSV export into a standard OHLCV DataFrame.

    HistData exports have **no header row** and use a fixed 7-column layout::

        2025.01.01,18:00,2625.098000,2626.005000,2624.355000,2625.048000,0

    Columns (positional): date, time, open, high, low, close, volume.

    Parameters
    ----------
    filepath:
        Path to the ``.csv`` file downloaded from HistData.com.
    symbol:
        Symbol name used for logging only, e.g. ``"XAUUSD"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``open``, ``high``, ``low``, ``close``, ``volume``.
        Index: ``time`` (``DatetimeTZDtype[UTC]``), sorted ascending.

    Raises
    ------
    FileNotFoundError
        If the file does not exist at ``filepath``.
    ValueError
        If the DataFrame is empty after parsing.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"HistData CSV not found: {path}")

    # Peek at the first line to detect whether a header row is present.
    # HistData files come in two flavours:
    #   no-header:   2025.01.01,18:00,2625.09,...
    #   with-header: Date,Time,Open,High,Low,Close,Volume
    with open(path, encoding="utf-8") as _f:
        first_line = _f.readline().strip()

    has_header = first_line.upper().startswith("DATE")

    if has_header:
        df = pd.read_csv(path, dtype=str)
        df.columns = [c.lower() for c in df.columns]
        # Rename 'date'/'time' if they came in as title-case
        df = df.rename(columns={"date": "date", "time": "time"})
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
    else:
        df = pd.read_csv(
            path,
            header=None,
            names=["date", "time", "open", "high", "low", "close", "volume"],
            dtype={"date": str, "time": str, "open": float, "high": float,
                   "low": float, "close": float, "volume": float},
        )

    if df.empty:
        raise ValueError(f"HistData CSV is empty: {path}")

    dt_index = pd.to_datetime(
        df["date"] + " " + df["time"],
        format="%Y.%m.%d %H:%M",
        utc=True,
    )
    df = df[["open", "high", "low", "close", "volume"]].copy()
    df.index = dt_index
    df.index.name = "time"
    df = df.sort_index()

    logger.info(
        "Loaded %d bars from HistData CSV: %s (%s to %s)",
        len(df),
        symbol,
        df.index[0],
        df.index[-1],
    )
    return df


def resample_ohlcv(df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
    """Resample an OHLCV DataFrame to a coarser timeframe.

    Uses standard OHLCV aggregation: open=first, high=max, low=min,
    close=last, volume=sum. Incomplete bars at the boundary are dropped.

    Parameters
    ----------
    df:
        OHLCV DataFrame with a UTC datetime index (as returned by
        :func:`load_histdata_csv`, :func:`load_dukascopy_csv`, or
        :func:`load_parquet`).
    target_timeframe:
        Target timeframe string, e.g. ``"H1"``, ``"M15"``.
        Must be one of: M1, M5, M15, M30, H1, H2, H4, D1, W1.

    Returns
    -------
    pd.DataFrame
        Resampled OHLCV DataFrame with the same column layout as the input.

    Raises
    ------
    ValueError
        If ``target_timeframe`` is not a recognised timeframe string.
    """
    rule = _TF_TO_PANDAS.get(target_timeframe)
    if rule is None:
        raise ValueError(
            f"Unknown target_timeframe {target_timeframe!r}. "
            f"Valid options: {list(_TF_TO_PANDAS)}"
        )

    resampled = (
        df.resample(rule, label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
    )
    resampled.index.name = "time"

    logger.info(
        "Resampled %d bars → %d %s bars",
        len(df),
        len(resampled),
        target_timeframe,
    )
    return resampled


def load_csv(filepath: str | Path, symbol: str) -> pd.DataFrame:
    """Load an OHLCV CSV file, auto-detecting Dukascopy or HistData format.

    Tries Dukascopy format first (header-based detection). Falls back to
    HistData.com MetaTrader format (headerless) if no recognised time column
    is found.

    Parameters
    ----------
    filepath:
        Path to the CSV file.
    symbol:
        Symbol name used for logging, e.g. ``"XAUUSD"``.

    Returns
    -------
    pd.DataFrame
        Standard OHLCV DataFrame with UTC datetime index.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file cannot be parsed in either format.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    try:
        return load_dukascopy_csv(path, symbol, timeframe="")
    except ValueError:
        logger.debug("Dukascopy parse failed, trying HistData format: %s", path)
        return load_histdata_csv(path, symbol)


def detect_timeframe_from_df(df: pd.DataFrame) -> str:
    """Infer the bar timeframe by examining the median interval between rows.

    Computes the median timedelta between consecutive bar timestamps and maps
    it to the nearest standard timeframe label.

    Parameters
    ----------
    df:
        OHLCV DataFrame with a UTC datetime index (as returned by
        :func:`load_dukascopy_csv` or :func:`load_parquet`).

    Returns
    -------
    str
        One of ``"M1"``, ``"M5"``, ``"M15"``, ``"M30"``, ``"H1"``,
        ``"H4"``, ``"D1"``, ``"W1"``. Falls back to ``"H1"`` if the
        DataFrame has fewer than two rows or detection is inconclusive.
    """
    if len(df) < 2:
        return "H1"

    deltas = df.index.to_series().diff().dropna()
    median_minutes = deltas.median().total_seconds() / 60

    _TF_MAP = [
        (1,     "M1"),
        (5,     "M5"),
        (15,    "M15"),
        (30,    "M30"),
        (45,    "M45"),
        (60,    "H1"),
        (120,   "H2"),
        (240,   "H4"),
        (1440,  "D1"),
        (10080, "W1"),
    ]

    best = "H1"
    min_diff = float("inf")
    for minutes, label in _TF_MAP:
        diff = abs(median_minutes - minutes)
        if diff < min_diff:
            min_diff = diff
            best = label

    logger.debug("Detected timeframe %s from median interval %.1f min", best, median_minutes)
    return best
