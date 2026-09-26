"""单标的多头持仓状态。"""

from dataclasses import dataclass

from quant.core.validation import validate_non_negative_finite, validate_symbol


@dataclass
class Position:
    """由 Portfolio 持有并更新的单标的多头持仓状态。"""

    symbol: str
    quantity: float = 0.0
    average_price: float = 0.0
    realized_pnl: float = 0.0

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_non_negative_finite(self.quantity, "quantity")
        validate_non_negative_finite(self.average_price, "average_price")
        if self.quantity > 0 and self.average_price <= 0:
            raise ValueError("非空持仓必须具有正的平均成本。")

    def market_value(self, price: float) -> float:
        """按给定估值价格计算市值；市值不作为可变状态重复保存。"""
        validate_non_negative_finite(price, "price")
        return self.quantity * price
