"""单标的多头 ATR 保护止损状态与日线触发判断。"""

from datetime import datetime
from typing import Optional

from quant.core.bar import Bar
from quant.core.validation import validate_datetime, validate_positive_finite


class AtrStopPolicy:
    """成交后以实际买入价固定止损；支持跳空及日内触发，不做追踪止损。"""

    def __init__(self) -> None:
        self.stop_price: Optional[float] = None
        self.signal_time: Optional[datetime] = None

    def activate(self, entry_price: float, distance: float, signal_time: datetime) -> None:
        """在买入成交入账后锚定止损价。"""
        validate_positive_finite(entry_price, "entry_price")
        validate_positive_finite(distance, "distance")
        validate_datetime(signal_time, "signal_time")
        stop_price = entry_price - distance
        validate_positive_finite(stop_price, "stop_price")
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
