"""佣金计算模型。"""

from typing import Protocol

from quant.core.validation import validate_non_negative_finite, validate_positive_finite

DEFAULT_COMMISSION_RATE = 0.0003

class CommissionModel(Protocol):
    def calculate(self, price: float, quantity: float) -> float:
        """返回该笔成交的费用；数量报价要求费用随数量单调不减。"""
        ...


class PercentageCommission:
    """按实际成交金额收取比例佣金。"""

    def __init__(self, rate: float) -> None:
        validate_non_negative_finite(rate, "rate")
        if rate >= 1:
            raise ValueError("佣金率必须是 [0, 1) 范围内的有限数。")
        self.rate = float(rate)

    def calculate(self, price: float, quantity: float) -> float:
        """按成交金额计费；实际 Trade 只记录一次最终成交费用。"""
        validate_positive_finite(price, "price")
        validate_non_negative_finite(quantity, "quantity")
        fee = price * quantity * self.rate
        validate_non_negative_finite(fee, "commission")
        return fee


class FixedCommission:
    """每笔成交收取固定费用。"""

    def __init__(self, amount: float) -> None:
        validate_non_negative_finite(amount, "amount")
        self.amount = float(amount)

    def calculate(self, price: float, quantity: float) -> float:
        """每笔成交收取固定费用，与成交数量无关。"""
        validate_positive_finite(price, "price")
        validate_non_negative_finite(quantity, "quantity")
        return self.amount
