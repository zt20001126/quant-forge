"""成交滑点模型。"""

from typing import Protocol

from quant.core.enums import Side
from quant.core.validation import validate_non_negative_finite, validate_positive_finite


class SlippageModel(Protocol):
    def apply(self, price: float, side: Side) -> float:
        """按买卖方向调整参考价；买入不应获得更优价格，卖出亦然。"""
        ...


class NoSlippage:
    """成交价直接使用市场参考价。"""

    def apply(self, price: float, side: Side) -> float:
        """返回未经成本调整的参考价。"""
        validate_positive_finite(price, "price")
        if not isinstance(side, Side):
            raise ValueError("side 必须是 Side 枚举。")
        return price


class FixedSlippage:
    """按买卖方向施加固定价格偏移。"""

    def __init__(self, amount: float) -> None:
        validate_non_negative_finite(amount, "amount")
        self.amount = float(amount)

    def apply(self, price: float, side: Side) -> float:
        """买入提高、卖出降低参考价，以表达不利成交方向。"""
        validate_positive_finite(price, "price")
        if not isinstance(side, Side):
            raise ValueError("side 必须是 Side 枚举。")
        return price + self.amount if side == Side.BUY else price - self.amount


class PercentageSlippage:
    """按参考价比例施加不利成交价格。"""

    def __init__(self, rate: float) -> None:
        validate_non_negative_finite(rate, "rate")
        if rate >= 1:
            raise ValueError("滑点率必须是 [0, 1) 范围内的有限数。")
        self.rate = float(rate)

    def apply(self, price: float, side: Side) -> float:
        """买入上浮、卖出下浮；费率不进入账户记账。"""
        validate_positive_finite(price, "price")
        if not isinstance(side, Side):
            raise ValueError("side 必须是 Side 枚举。")
        factor = 1 + self.rate if side == Side.BUY else 1 - self.rate
        return price * factor
