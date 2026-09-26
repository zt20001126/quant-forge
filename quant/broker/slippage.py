"""成交滑点模型。"""

from typing import Protocol
import math

from quant.core.enums import Side


class SlippageModel(Protocol):
    def apply(self, price: float, side: Side) -> float:
        ...


class NoSlippage:
    def apply(self, price: float, side: Side) -> float:
        return price


class FixedSlippage:
    def __init__(self, amount: float) -> None:
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("固定滑点必须是有限非负数。")
        self.amount = float(amount)

    def apply(self, price: float, side: Side) -> float:
        return price + self.amount if side == Side.BUY else price - self.amount


class PercentageSlippage:
    def __init__(self, rate: float) -> None:
        if not math.isfinite(rate) or rate < 0 or rate >= 1:
            raise ValueError("滑点率必须是 [0, 1) 范围内的有限数。")
        self.rate = float(rate)

    def apply(self, price: float, side: Side) -> float:
        factor = 1 + self.rate if side == Side.BUY else 1 - self.rate
        return price * factor
