"""逐 Bar 策略接口。"""

from __future__ import annotations

from typing import Protocol, Sequence

from quant.core.bar import Bar
from quant.core.order import OrderIntent


class Strategy(Protocol):
    def on_bar(self, bar: Bar, history: Sequence[Bar]) -> list[OrderIntent]:
        """处理截至当前 Bar 的历史信息并生成交易意图。"""
        ...
