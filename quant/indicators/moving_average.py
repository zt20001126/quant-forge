"""简单移动平均指标。"""

from __future__ import annotations

import math
from typing import Optional, Sequence


def simple_moving_average(values: Sequence[float], window: int) -> list[Optional[float]]:
    """返回滚动简单均线；窗口未满的位置为 None。"""
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise ValueError("均线窗口必须是正整数。")
    result: list[Optional[float]] = []
    rolling_sum = 0.0
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("指标输入必须是有限数值。")
        rolling_sum += float(value)
        if index >= window:
            rolling_sum -= float(values[index - window])
        result.append(rolling_sum / window if index >= window - 1 else None)
    return result
