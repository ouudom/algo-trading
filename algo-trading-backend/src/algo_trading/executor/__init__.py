"""
executor - Live order placement and management via MetaTrader 5.
"""

from .executor import close_order, place_order

__all__ = ["place_order", "close_order"]
