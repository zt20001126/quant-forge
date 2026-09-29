"""领域对象共享的基础校验。"""

import math
from datetime import datetime


def validate_symbol(symbol: str) -> None:
    """拒绝空白或非字符串标的代码。"""
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("标的代码不能为空。")


def validate_datetime(value: datetime, name: str) -> None:
    """校验领域时间字段的类型。"""
    if not isinstance(value, datetime):
        raise TypeError("{} 必须是 datetime。".format(name))


def validate_finite(value: float, name: str) -> None:
    """校验有限数值；布尔值不能代替金额、价格或数量。"""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError("{} 必须是有限数值。".format(name))


def validate_positive_finite(value: float, name: str) -> None:
    """校验价格、数量等必须严格大于零的字段。"""
    validate_finite(value, name)
    if value <= 0:
        raise ValueError("{} 必须是有限正数。".format(name))


def validate_non_negative_finite(value: float, name: str) -> None:
    """校验现金、费用等允许零值的字段。"""
    validate_finite(value, name)
    if value < 0:
        raise ValueError("{} 必须是有限非负数。".format(name))
