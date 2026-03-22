"""
configs/settings.py - Centralised application configuration via Pydantic BaseSettings.

All settings can be overridden by environment variables or a ``.env`` file in
the project root.  Sensitive values (passwords, tokens) must never be
hard-coded; they must come from the environment.

Usage::

    from configs.settings import get_settings
    settings = get_settings()
    print(settings.DATABASE_URL)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings.

    Attributes
    ----------
    DATABASE_URL:
        Async PostgreSQL connection string.
        Example: ``postgresql+asyncpg://user:pass@localhost:5432/algotrader``
    DB_ECHO:
        If True, SQLAlchemy will log all SQL statements. Useful for development.
    MT5_LOGIN:
        MetaTrader 5 account number (integer).
    MT5_PASSWORD:
        MetaTrader 5 account password.
    MT5_SERVER:
        MetaTrader 5 broker server name, e.g. ``"ICMarkets-Demo"``.
    TRADING_MODE:
        One of ``"backtest"``, ``"paper"``, or ``"live"``.
    SUPPORTED_SYMBOLS:
        Comma-separated list of tradeable instruments.
    SUPPORTED_TIMEFRAMES:
        Comma-separated list of supported bar timeframes.
    RISK_PCT:
        Fraction of equity to risk per trade (e.g. ``0.01`` for 1 %).
    MAX_DAILY_LOSS_PCT:
        Daily loss circuit-breaker threshold (e.g. ``0.03`` for 3 %).
    MAX_DRAWDOWN_PCT:
        Drawdown circuit-breaker threshold (e.g. ``0.10`` for 10 %).
    CORS_ORIGINS:
        Additional allowed CORS origins beyond localhost:3000.
    SECRET_KEY:
        Application secret key (reserved for future JWT auth).
    LOG_LEVEL:
        Python logging level name. Default ``"INFO"``.
    DATA_DIR:
        Base directory for raw, processed, and Parquet data files.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- Database ----------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://algotrader:algotrader@localhost:5432/algotrader",
        description="Async PostgreSQL DSN (asyncpg driver).",
    )
    DB_ECHO: bool = Field(default=False, description="Enable SQLAlchemy SQL logging.")

    # ---- MetaTrader 5 ------------------------------------------------------
    MT5_LOGIN: int = Field(default=0, description="MT5 account number.")
    MT5_PASSWORD: str = Field(default="", description="MT5 account password.")
    MT5_SERVER: str = Field(default="", description="MT5 broker server name.")
    MT5_TIMEOUT: int = Field(default=60_000, description="MT5 connection timeout in ms.")
    MT5_HOST: str = Field(default="127.0.0.1", description="mt5linux bridge host (Linux only).")
    MT5_PORT: int = Field(default=18812, description="mt5linux bridge port (Linux only).")

    # ---- Telegram notifications --------------------------------------------
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram bot token for trade alerts.")
    TELEGRAM_CHAT_ID: str = Field(default="", description="Telegram chat/channel ID for alerts.")

    # ---- Trading -----------------------------------------------------------
    TRADING_MODE: str = Field(
        default="backtest",
        description="Operating mode: 'backtest', 'paper', or 'live'.",
    )
    SUPPORTED_SYMBOLS: list[str] = Field(
        default=["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
        description="Instruments available for trading / backtesting.",
    )
    SUPPORTED_TIMEFRAMES: list[str] = Field(
        default=["H1"],
        description="Bar timeframes supported by the strategy.",
    )

    # ---- Risk parameters ---------------------------------------------------
    RISK_PCT: float = Field(default=0.01, ge=0.001, le=0.10)
    MAX_DAILY_LOSS_PCT: float = Field(default=0.03, ge=0.005, le=0.20)
    MAX_DRAWDOWN_PCT: float = Field(default=0.10, ge=0.01, le=0.50)

    # ---- API ---------------------------------------------------------------
    CORS_ORIGINS: list[str] = Field(
        default=[],
        description="Additional CORS origins beyond localhost:3000.",
    )
    SECRET_KEY: str = Field(
        default="change-me-in-production",
        description="Application secret key. Override in .env!",
    )

    # ---- Observability -----------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO", description="Python logging level.")

    # ---- Storage -----------------------------------------------------------
    DATA_DIR: str = Field(default="data", description="Base directory for data files.")
    PARQUET_DIR: str = Field(default="data/parquet")
    RAW_DIR: str = Field(default="data/raw")
    PROCESSED_DIR: str = Field(default="data/processed")

    @field_validator("TRADING_MODE")
    @classmethod
    def validate_trading_mode(cls, v: str) -> str:
        allowed = {"backtest", "paper", "live"}
        if v not in allowed:
            raise ValueError(f"TRADING_MODE must be one of {allowed}, got {v!r}")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        import logging
        numeric = getattr(logging, v.upper(), None)
        if not isinstance(numeric, int):
            raise ValueError(f"Invalid LOG_LEVEL: {v!r}")
        return v.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    The ``@lru_cache`` decorator ensures the ``.env`` file is parsed only once
    per process, which is important for performance in FastAPI's dependency
    injection system.
    """
    return Settings()
