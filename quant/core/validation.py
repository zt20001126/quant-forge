"""领域对象共享的基础校验。"""

import math
from datetime import datetime


def validate_symbol(symbol: str) -> None:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("标的代码不能为空。")


def validate_datetime(value: datetime, name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError("{} 必须是 datetime。".format(name))


def validate_positive_finite(value: float, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError("{} 必须是有限正数。".format(name))


def validate_non_negative_finite(value: float, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError("{} 必须是有限非负数。".format(name))
