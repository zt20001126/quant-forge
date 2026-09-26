"""佣金计算模型。"""

import math
from typing import Protocol


class CommissionModel(Protocol):
    def calculate(self, price: float, quantity: float) -> float:
        ...


class PercentageCommission:
    def __init__(self, rate: float) -> None:
        if not math.isfinite(rate) or rate < 0 or rate >= 1:
            raise ValueError("佣金率必须是 [0, 1) 范围内的有限数。")
        self.rate = float(rate)

    def calculate(self, price: float, quantity: float) -> float:
        return price * quantity * self.rate


class FixedCommission:
    def __init__(self, amount: float) -> None:
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("固定佣金必须是有限非负数。")
        self.amount = float(amount)

    def calculate(self, price: float, quantity: float) -> float:
        return self.amount
