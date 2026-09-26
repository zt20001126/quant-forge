"""协调行情、策略、Broker 与 Portfolio 的单标的日线回测。"""

from __future__ import annotations

from typing import Optional, Sequence

from quant.broker.broker import SimulatedBroker
from quant.core.bar import Bar
from quant.core.enums import OrderStatus, OrderType, Side
from quant.core.order import Order, OrderIntent, OrderResult
from quant.core.trade import Trade
from quant.data.base import DataFeed
from quant.engine.models import BacktestResult, EquitySnapshot, PendingOrder
from quant.portfolio.portfolio import Portfolio
from quant.strategy.base import Strategy


class BacktestEngine:
    """编排单标的日线回测，不实现策略、成交或绩效公式。"""

    def __init__(
        self,
        data_feed: DataFeed,
        strategy: Strategy,
        broker: SimulatedBroker,
        portfolio: Portfolio,
    ) -> None:
        self.data_feed = data_feed
        self.strategy = strategy
        self.broker = broker
        self.portfolio = portfolio
        self._has_run = False

    def run(self) -> BacktestResult:
        """执行生命周期：先处理前一根信号，再估值并读取当前 Bar 产生新信号。"""
        if self._has_run:
            raise RuntimeError("BacktestEngine 实例只能运行一次；重复回测请重新创建协作者。")
        self._has_run = True
        bars = list(self.data_feed)
        self._validate_bars(bars)
        history: list[Bar] = []
        pending: list[OrderIntent] = []
        terminal_pending: list[PendingOrder] = []
        next_order_number = 1
        trades: list[Trade] = []
        order_results: list[OrderResult] = []
        equity: list[EquitySnapshot] = []

        for bar_index, bar in enumerate(bars):
            due_intents = pending
            pending = []
            for intent in due_intents:
                # 意图来自上一根完整收盘 Bar；本根 Open 执行，避免同收盘前视。
                order = self._create_order(intent, bar, "order-{:06d}".format(next_order_number))
                if order is None:
                    target_holding = self.portfolio.position_quantity > 0
                    if intent.target_fraction != (1 if target_holding else 0):
                        order_results.append(
                            OrderResult(
                                "order-{:06d}".format(next_order_number),
                                OrderStatus.REJECTED,
                                "当前资金或持仓无法形成有效数量的订单。",
                            )
                        )
                        next_order_number += 1
                    continue
                next_order_number += 1
                result = self.broker.execute(order, bar)
                order_results.append(result)
                if result.status == OrderStatus.FILLED and result.trade is not None:
                    try:
                        self.portfolio.apply_trade(result.trade)
                    except ValueError as exc:
                        rejected = OrderResult(order.order_id, OrderStatus.REJECTED, str(exc))
                        order_results[-1] = rejected
                    else:
                        trades.append(result.trade)

            # 当日成交入账后按 Close 估值，快照因此同时反映成交与收盘市值。
            account = self.portfolio.mark_to_market(bar.close)
            equity.append(
                EquitySnapshot(
                    timestamp=bar.datetime,
                    cash=account.cash,
                    symbol=bar.symbol,
                    quantity=account.quantity,
                    close_price=bar.close,
                    market_value=account.market_value,
                    portfolio_value=account.portfolio_value,
                )
            )

            intents = self.strategy.on_bar(bar, tuple(history))
            for intent in intents:
                if bar_index + 1 < len(bars):
                    pending.append(intent)
                    continue
                if intent.target_fraction != (1 if self.portfolio.position_quantity > 0 else 0):
                    side = Side.BUY if intent.target_fraction == 1 else Side.SELL
                    terminal_pending.append(
                        PendingOrder(
                            order_id="expired-{:06d}".format(next_order_number),
                            symbol=intent.symbol,
                            side=side,
                            quantity=None if side == Side.BUY else self.portfolio.position_quantity,
                            signal_time=intent.signal_time,
                            status="EXPIRED_NO_NEXT_BAR",
                        )
                    )
                    next_order_number += 1
            history.append(bar)

        return BacktestResult(
            initial_cash=self.portfolio.initial_cash,
            trades=tuple(trades),
            equity_curve=tuple(equity),
            order_results=tuple(order_results),
            pending_orders=tuple(terminal_pending),
        )

    def _create_order(self, intent: OrderIntent, bar: Bar, order_id: str) -> Optional[Order]:
        """执行时才按当前 Open 和账户现金确定数量，不读取未来价格。"""
        if intent.signal_time >= bar.datetime:
            raise ValueError("订单只能在信号之后的 Bar 执行。")
        if intent.symbol != bar.symbol:
            raise ValueError("策略意图标的必须匹配当前 Bar。")
        current_quantity = self.portfolio.position_quantity
        side = Side.BUY if intent.target_fraction == 1 else Side.SELL
        if intent.target_fraction == 1 and current_quantity > 0:
            return None
        if intent.target_fraction == 0 and current_quantity <= 0:
            return None

        execution_reference = bar.open
        quoted_price = self.broker.quote(side, execution_reference)
        quantity = (
            self.broker.max_affordable_quantity(self.portfolio.cash, quoted_price)
            if side == Side.BUY
            else current_quantity
        )
        if quantity <= 0:
            return None
        return Order(
            order_id=order_id,
            symbol=intent.symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.MARKET,
            signal_time=intent.signal_time,
            execution_time=bar.datetime,
        )

    def _validate_bars(self, bars: Sequence[Bar]) -> None:
        if not bars:
            raise ValueError("回测行情不能为空。")
        symbol = bars[0].symbol
        previous = None
        for bar in bars:
            if bar.symbol != symbol or bar.symbol != self.portfolio.symbol:
                raise ValueError("V0.1 仅支持一个且与账户一致的标的。")
            if previous is not None and bar.datetime <= previous:
                raise ValueError("行情时间必须严格递增且无重复。")
            previous = bar.datetime
