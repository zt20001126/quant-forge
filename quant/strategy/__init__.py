"""策略接口及实现。"""

from quant.strategy.base import Strategy
from quant.strategy.ma_cross import MACrossStrategy

__all__ = ["Strategy", "MACrossStrategy"]
