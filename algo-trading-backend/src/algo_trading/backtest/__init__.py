"""
backtest - Event-driven backtesting engine for the MA-Crossover + ATR strategy.
"""

from .backtest import BacktestResult, run_backtest

__all__ = ["run_backtest", "BacktestResult"]
