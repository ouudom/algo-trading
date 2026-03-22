"""
signal - MA Crossover + ATR Filter signal generation for AlgoTrader.
"""

from .signal import generate_rsi_signals, generate_signals, RsiSignalParams

__all__ = ["generate_signals", "generate_rsi_signals", "RsiSignalParams"]
