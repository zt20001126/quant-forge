"""双均线方向策略，表达多头或空仓目标。"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from quant.core.bar import Bar
from quant.core.order import OrderIntent
from quant.indicators.average_true_range import average_true_range
from quant.indicators.moving_average import simple_moving_average


class MACrossStrategy:
    """依据截至当前 Bar 的均线产生方向意图，不决定投入比例。"""

    def __init__(
        self,
        short_window: int = 5,
        long_window: int = 20,
        atr_period: Optional[int] = None,
        atr_multiplier: Optional[float] = None,
    ) -> None:
        if (
            isinstance(short_window, bool) or not isinstance(short_window, int)
            or isinstance(long_window, bool) or not isinstance(long_window, int)
        ):
            raise ValueError("均线窗口必须是正整数。")
        if short_window <= 0 or long_window <= 0 or short_window >= long_window:
            raise ValueError("均线窗口必须为正整数，且短期窗口小于长期窗口。")
        self.short_window = short_window
        self.long_window = long_window
        if (atr_period is None) != (atr_multiplier is None):
            raise ValueError("atr_period 与 atr_multiplier 必须同时配置。")
        if atr_period is not None and (
            isinstance(atr_period, bool) or not isinstance(atr_period, int) or atr_period <= 0
        ):
            raise ValueError("atr_period 必须是正整数。")
        if atr_multiplier is not None and (
            isinstance(atr_multiplier, bool) or not isinstance(atr_multiplier, (int, float))
            or not 0 < atr_multiplier < float("inf")
        ):
            raise ValueError("atr_multiplier 必须是正的有限数值。")
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self._last_target: Optional[int] = None

    def on_bar(self, bar: Bar, history: Sequence[Bar]) -> list[OrderIntent]:
        """只使用当前及过去 Bar；当前收盘信号留待后续 Bar 执行。"""
        bars = list(history)
        if not bars or bars[-1] != bar:
            bars.append(bar)
        closes = [item.close for item in bars if item.symbol == bar.symbol]
        # SMA 只需要最近一个窗口；避免每根 Bar 重算全部历史均线。
        short_values = simple_moving_average(closes[-self.short_window:], self.short_window)
        long_values = simple_moving_average(closes[-self.long_window:], self.long_window)
        short_value = short_values[-1]
        long_value = long_values[-1]
        if short_value is None or long_value is None:
            return []

        target = 1 if short_value > long_value else 0
        if target == self._last_target:
            return []
        stop_distance: Optional[float] = None
        if target == 1 and self.atr_period is not None and self.atr_multiplier is not None:
            atr_value = average_true_range(bars, self.atr_period)[-1]
            if atr_value is None or atr_value <= 0:
                # 零波动是合法行情，但无法形成保护距离；保持目标以便之后重试。
                return []
            stop_distance = atr_value * self.atr_multiplier
            if not math.isfinite(stop_distance):
                raise ValueError("ATR 止损距离超出可表示的数值范围。")
        if self._last_target is None:
            self._last_target = target
            if target == 1:
                return [OrderIntent(bar.symbol, 1, bar.datetime, stop_distance)]
            return []
        self._last_target = target
        return [OrderIntent(bar.symbol, target, bar.datetime, stop_distance)]
