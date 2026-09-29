"""True Range 与 Wilder 平均真实波幅指标。"""

from __future__ import annotations

from typing import Optional, Sequence

from quant.core.bar import Bar


def true_range(bars: Sequence[Bar]) -> list[float]:
    """按时间顺序计算单一标的的 True Range 序列。

    第一根 Bar 没有前收盘价，因此 TR 使用 High - Low；后续 Bar 同时考虑
    当根振幅与前收盘的跳空距离，避免低估隔夜波动。
    """
    if not bars:
        return []

    symbol = bars[0].symbol
    previous: Optional[Bar] = None
    result: list[float] = []
    for bar in bars:
        if bar.symbol != symbol:
            raise ValueError("True Range 输入必须属于同一标的。")
        if previous is not None and bar.datetime <= previous.datetime:
            raise ValueError("True Range 输入必须按时间严格递增且无重复。")

        if previous is None:
            value = bar.high - bar.low
        else:
            value = max(
                bar.high - bar.low,
                abs(bar.high - previous.close),
                abs(bar.low - previous.close),
            )
        result.append(value)
        previous = bar
    return result


def average_true_range(bars: Sequence[Bar], period: int) -> list[Optional[float]]:
    """计算 Wilder ATR；前 ``period - 1`` 根 Bar 用 None 表示尚未就绪。

    首个 ATR 是前 ``period`` 个 TR 的简单平均，后续按
    ``((period - 1) * 前值 + 当前 TR) / period`` 平滑。计算只使用当前及
    过去 Bar，不会读取未来行情。
    """
    if isinstance(period, bool) or not isinstance(period, int) or period <= 0:
        raise ValueError("ATR 周期必须是正整数。")

    ranges = true_range(bars)
    result: list[Optional[float]] = [None] * len(ranges)
    if len(ranges) < period:
        return result

    atr_value = sum(ranges[:period]) / period
    result[period - 1] = atr_value
    for index in range(period, len(ranges)):
        atr_value = ((period - 1) * atr_value + ranges[index]) / period
        result[index] = atr_value
    return result
