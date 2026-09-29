"""组合仓位数量计算边界及固定比例实现。"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from typing import Optional, Protocol


class PositionSizer(Protocol):
    """根据账户权益与执行价格计算整数买入数量。"""

    def allocation_budget(self, equity: float) -> Decimal:
        """返回含买入费用的资金额度；风险预算另由数量公式约束。"""
        ...

    def calculate_quantity(
        self, equity: float, price: float, stop_distance: Optional[float] = None
    ) -> int:
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
        self._ratio = ratio

    @property
    def position_ratio(self) -> float:
        """只读资金比例；修改配置应重新创建仓位器。"""
        return float(self._ratio)

    def allocation_budget(self, equity: float) -> Decimal:
        """返回可投入本金与买入费用的总额度。"""
        try:
            equity_value = Decimal(str(equity))
        except (InvalidOperation, ValueError):
            return Decimal(0)
        if not equity_value.is_finite() or equity_value <= 0:
            return Decimal(0)
        return equity_value * self._ratio

    def calculate_quantity(
        self, equity: float, price: float, stop_distance: Optional[float] = None
    ) -> int:
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


class RiskBasedPositionSizer:
    """按权益风险预算与止损距离计算整股数量。"""

    def __init__(self, risk_fraction: float = 0.01) -> None:
        if isinstance(risk_fraction, bool) or not isinstance(risk_fraction, (int, float)):
            raise ValueError("risk_fraction 必须是 (0, 1] 内的有限数值。")
        try:
            risk = Decimal(str(risk_fraction))
        except InvalidOperation as exc:
            raise ValueError("risk_fraction 必须是有限数值。") from exc
        if not risk.is_finite() or not 0 < risk <= 1:
            raise ValueError("risk_fraction 必须是 (0, 1] 内的有限数值。")
        self._risk = risk

    @property
    def risk_fraction(self) -> float:
        """只读风险比例，与内部十进制计算使用同一份配置。"""
        return float(self._risk)

    def allocation_budget(self, equity: float) -> Decimal:
        """风险仓位仍可使用全部可用权益，实际数量另受风险预算限制。"""
        try:
            equity_value = Decimal(str(equity))
        except (InvalidOperation, ValueError):
            return Decimal(0)
        return max(Decimal(0), equity_value) if equity_value.is_finite() else Decimal(0)

    def calculate_quantity(
        self, equity: float, price: float, stop_distance: Optional[float] = None
    ) -> int:
        """以 floor(Equity × RiskFraction / StopDistance) 计算数量。"""
        if stop_distance is None:
            raise ValueError("风险定仓必须提供有效的 stop_distance。")
        try:
            equity_value = Decimal(str(equity))
            price_value = Decimal(str(price))
            distance_value = Decimal(str(stop_distance))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("权益、价格和止损距离必须是有限数值。") from exc
        if not distance_value.is_finite() or distance_value <= 0:
            raise ValueError("stop_distance 必须是正的有限数值。")
        if (
            not equity_value.is_finite()
            or not price_value.is_finite()
            or equity_value <= 0
            or price_value <= 0
        ):
            return 0
        budget = equity_value * self._risk
        return int((budget / distance_value).to_integral_value(rounding=ROUND_FLOOR))
