"""V0.1 单标的、不做空的账户状态。"""

from __future__ import annotations

from dataclasses import dataclass
from quant.core.enums import Side
from quant.core.position import Position
from quant.core.trade import Trade
from quant.core.validation import validate_positive_finite


@dataclass(frozen=True)
class AccountSnapshot:
    cash: float
    symbol: str
    quantity: float
    average_price: float
    mark_price: float
    market_value: float
    portfolio_value: float


class Portfolio:
    def __init__(self, initial_cash: float, symbol: str) -> None:
        validate_positive_finite(initial_cash, "initial_cash")
        if not symbol or not symbol.strip():
            raise ValueError("标的代码不能为空。")
        self.initial_cash = float(initial_cash)
        self._cash = float(initial_cash)
        self._position = Position(symbol=symbol)
        self._applied_trade_ids: set[str] = set()

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def symbol(self) -> str:
        return self._position.symbol

    @property
    def position_quantity(self) -> float:
        return self._position.quantity

    def apply_trade(self, trade: Trade) -> None:
        if trade.symbol != self.symbol:
            raise ValueError("成交标的与账户标的不一致。")
        if trade.trade_id in self._applied_trade_ids:
            raise ValueError("重复入账的 Trade。")
        amount = trade.price * trade.quantity
        if trade.side == Side.BUY:
            total_cost = amount + trade.commission
            if total_cost > self._cash + 1e-8:
                raise ValueError("账户现金不足，拒绝买入成交。")
            new_quantity = self._position.quantity + trade.quantity
            self._position.average_price = (
                self._position.quantity * self._position.average_price + total_cost
            ) / new_quantity
            self._position.quantity = new_quantity
            self._cash -= total_cost
            if abs(self._cash) < 1e-8:
                self._cash = 0.0
        else:
            if trade.quantity > self._position.quantity + 1e-8:
                raise ValueError("卖出数量超过持仓，禁止做空。")
            if self._cash + amount - trade.commission < -1e-8:
                raise ValueError("卖出费用超过可用资金，拒绝入账。")
            realized = (trade.price - self._position.average_price) * trade.quantity - trade.commission
            self._position.realized_pnl += realized
            self._cash += amount - trade.commission
            self._position.quantity -= trade.quantity
            if self._position.quantity <= 1e-8:
                self._position.quantity = 0.0
                self._position.average_price = 0.0
        self._applied_trade_ids.add(trade.trade_id)

    def mark_to_market(self, price: float) -> AccountSnapshot:
        validate_positive_finite(price, "price")
        market_value = self._position.market_value(price)
        return AccountSnapshot(
            cash=self._cash,
            symbol=self.symbol,
            quantity=self._position.quantity,
            average_price=self._position.average_price,
            mark_price=price,
            market_value=market_value,
            portfolio_value=self._cash + market_value,
        )
