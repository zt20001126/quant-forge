"""单标的多头 ATR 保护止损状态与日线触发判断。"""

from datetime import datetime
from typing import Optional

from quant.core.bar import Bar


class AtrStopPolicy:
    """成交后以实际买入价固定止损；支持跳空及日内触发，不做追踪止损。"""

    def __init__(self) -> None:
        self.stop_price: Optional[float] = None
        self.signal_time: Optional[datetime] = None

    def activate(self, entry_price: float, distance: float, signal_time: datetime) -> None:
        """在买入成交入账后锚定止损价。"""
        stop_price = entry_price - distance
        if stop_price <= 0:
            raise ValueError("ATR 止损价必须为正数。")
        self.stop_price = stop_price
        self.signal_time = signal_time

    def trigger_reference(self, bar: Bar) -> Optional[float]:
        """未触发返回 None；跳空穿越用 Open，盘中触及用 stop_price。"""
        if self.stop_price is None:
            return None
        if bar.open <= self.stop_price:
            return bar.open
        if bar.low <= self.stop_price:
            return self.stop_price
        return None

    def clear(self) -> None:
        """清仓后移除活动止损。"""
        self.stop_price = None
        self.signal_time = None
