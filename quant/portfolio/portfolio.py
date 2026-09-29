"""V0.1 单标的、不做空的账户状态。"""

from __future__ import annotations

from dataclasses import dataclass

from quant.core.enums import Side
from quant.core.position import Position
from quant.core.trade import Trade
from quant.core.validation import (
    validate_finite,
    validate_non_negative_finite,
    validate_positive_finite,
    validate_symbol,
)

CASH_ROUNDING_TOLERANCE = 1e-8


@dataclass(frozen=True)
class AccountSnapshot:
    """账户只读估值；average_price 为含买入佣金的平均成本。"""

    cash: float
    symbol: str
    quantity: float
    average_price: float
    mark_price: float
    market_value: float
    portfolio_value: float


class Portfolio:
    """V0.1 账户状态唯一所有者，维护现金、单标的持仓并负责估值。"""

    def __init__(self, initial_cash: float, symbol: str) -> None:
        validate_positive_finite(initial_cash, "initial_cash")
        validate_symbol(symbol)
        self.initial_cash = float(initial_cash)
        self._cash = float(initial_cash)
        self._position = Position(symbol=symbol)
        self._applied_trade_ids: set[str] = set()

    @property
    def cash(self) -> float:
        """返回可用现金；账户只能通过 Trade 入账更新。"""
        return self._cash

    @property
    def symbol(self) -> str:
        """返回账户唯一标的。"""
        return self._position.symbol

    @property
    def position_quantity(self) -> float:
        """返回当前多头数量。"""
        return self._position.quantity

    def apply_trade(self, trade: Trade) -> None:
        """根据已经成交的 Trade 更新现金与持仓，不自行判断成交。"""
        if trade.symbol != self.symbol:
            raise ValueError("成交标的与账户标的不一致。")
        if trade.trade_id in self._applied_trade_ids:
            raise ValueError("重复入账的 Trade。")
        amount = trade.price * trade.quantity
        validate_non_negative_finite(amount, "trade_value")
        if trade.side == Side.BUY:
            # 买入成本含佣金，按含费成本更新均价，保证现金和持仓账面一致。
            total_cost = amount + trade.commission
            validate_non_negative_finite(total_cost, "total_cost")
            if total_cost > self._cash + CASH_ROUNDING_TOLERANCE:
                raise ValueError("账户现金不足，拒绝买入成交。")
            new_quantity = self._position.quantity + trade.quantity
            validate_positive_finite(new_quantity, "position_quantity")
            average_price = (
                self._position.quantity * self._position.average_price + total_cost
            ) / new_quantity
            validate_positive_finite(average_price, "average_price")
            self._position.average_price = average_price
            self._position.quantity = new_quantity
            self._cash = max(0.0, self._cash - total_cost)
        else:
            # 卖出只减少已有持仓，手续费从回款中扣除并计入已实现盈亏。
            # 股数不能复用金额容差，否则会为实际不存在的持仓支付回款。
            if trade.quantity > self._position.quantity:
                raise ValueError("卖出数量超过持仓，禁止做空。")
            new_cash = self._cash + amount - trade.commission
            validate_finite(new_cash, "cash")
            if new_cash < -CASH_ROUNDING_TOLERANCE:
                raise ValueError("卖出费用超过可用资金，拒绝入账。")
            realized = (
                (trade.price - self._position.average_price) * trade.quantity
                - trade.commission
            )
            realized_pnl = self._position.realized_pnl + realized
            validate_finite(realized_pnl, "realized_pnl")
            self._position.realized_pnl = realized_pnl
            self._cash = max(0.0, new_cash)
            self._position.quantity -= trade.quantity
            # 小额剩余持仓仍有真实市值，只有恰好清仓才重置成本。
            if self._position.quantity == 0:
                self._position.quantity = 0.0
                self._position.average_price = 0.0
        self._applied_trade_ids.add(trade.trade_id)

    def mark_to_market(self, price: float) -> AccountSnapshot:
        """按行情价格估值；总资产等于现金加持仓市值，成本不随估值变化。"""
        validate_positive_finite(price, "price")
        market_value = self._position.market_value(price)
        portfolio_value = self._cash + market_value
        validate_non_negative_finite(portfolio_value, "portfolio_value")
        return AccountSnapshot(
            cash=self._cash,
            symbol=self.symbol,
            quantity=self._position.quantity,
            average_price=self._position.average_price,
            mark_price=price,
            market_value=market_value,
            portfolio_value=portfolio_value,
        )
