"""双均线交叉策略，目标仓位为满仓或空仓。"""

from __future__ import annotations

from typing import Optional, Sequence

from quant.core.bar import Bar
from quant.core.order import OrderIntent
from quant.indicators.moving_average import simple_moving_average


class MACrossStrategy:
    """依据截至当前 Bar 的收盘历史产生空仓/满仓目标意图。"""

    def __init__(self, short_window: int = 5, long_window: int = 20) -> None:
        if isinstance(short_window, bool) or isinstance(long_window, bool):
            raise ValueError("均线窗口必须是正整数。")
        if short_window <= 0 or long_window <= 0 or short_window >= long_window:
            raise ValueError("均线窗口必须为正整数，且短期窗口小于长期窗口。")
        self.short_window = short_window
        self.long_window = long_window
        self._last_target: Optional[int] = None

    def on_bar(self, bar: Bar, history: Sequence[Bar]) -> list[OrderIntent]:
        """只使用当前及过去 Bar；当前收盘信号留待后续 Bar 执行。"""
        bars = list(history)
        if not bars or bars[-1] != bar:
            bars.append(bar)
        closes = [item.close for item in bars if item.symbol == bar.symbol]
        short_values = simple_moving_average(closes, self.short_window)
        long_values = simple_moving_average(closes, self.long_window)
        short_value = short_values[-1]
        long_value = long_values[-1]
        if short_value is None or long_value is None:
            return []

        target = 1 if short_value > long_value else 0
        if self._last_target is None:
            self._last_target = target
            if target == 1:
                return [OrderIntent(bar.symbol, 1, bar.datetime)]
            return []
        if target == self._last_target:
            return []

        self._last_target = target
        return [OrderIntent(bar.symbol, target, bar.datetime)]
