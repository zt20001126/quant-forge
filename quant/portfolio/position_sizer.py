"""组合仓位数量计算边界及固定比例实现。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Protocol


class PositionSizer(Protocol):
    """根据账户权益与执行价格计算整数买入数量。"""

    position_ratio: float

    def calculate_quantity(self, equity: float, price: float) -> int:
        """返回买入数量；无有效资金或价格时返回零。"""
        ...


class FixedFractionPositionSizer:
    """将账户权益的固定比例分配给每次买入，并按整股向下取整。"""

    def __init__(self, position_ratio: float = 1.0) -> None:
        """创建固定比例仓位器；position_ratio 必须在 (0, 1] 范围内。"""
        if (
            isinstance(position_ratio, bool)
            or not isinstance(position_ratio, (int, float))
            or not 0 < position_ratio <= 1
        ):
            raise ValueError("position_ratio 必须大于 0 且不超过 1。")
        try:
            ratio = Decimal(str(position_ratio))
        except InvalidOperation as exc:
            raise ValueError("position_ratio 必须是有限数值。") from exc
        if not ratio.is_finite():
            raise ValueError("position_ratio 必须是有限数值。")
        self.position_ratio = float(position_ratio)
        self._ratio = ratio

    def calculate_quantity(self, equity: float, price: float) -> int:
        """按 floor(权益 × 比例 ÷ 价格) 计算整股数量。

        参数：
            equity：执行时按当前行情估算的账户总权益。
            price：包含滑点影响的预估执行价格。
        返回：
            不超过固定比例预算的非负整股数量。

        equity 或 price 非有限、非正时不生成买入数量；Decimal 字符串运算
        避免二进制浮点误差使数量向上越过配置仓位。
        """
        try:
            equity_value = Decimal(str(equity))
            price_value = Decimal(str(price))
        except (InvalidOperation, ValueError):
            return 0
        if (
            not equity_value.is_finite()
            or not price_value.is_finite()
            or equity_value <= 0
            or price_value <= 0
        ):
            return 0
        allocated = equity_value * self._ratio
        return int((allocated / price_value).to_integral_value(rounding=ROUND_FLOOR))
