"""
data_feed - OHLCV data ingestion from MetaTrader 5 and Parquet-based local storage.
"""

from .data_feed import fetch_ohlcv, load_parquet, save_parquet

__all__ = ["fetch_ohlcv", "save_parquet", "load_parquet"]
