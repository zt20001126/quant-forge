"""协调行情、策略、Broker 与 Portfolio 的单标的日线回测。"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional, Sequence

from quant.broker.broker import SimulatedBroker
from quant.core.bar import Bar
from quant.core.enums import OrderStatus, OrderType, Side
from quant.core.order import Order, OrderIntent, OrderResult
from quant.core.trade import Trade
from quant.data.base import DataFeed
from quant.engine.models import BacktestResult, EquitySnapshot, PendingOrder
from quant.portfolio.portfolio import Portfolio
from quant.portfolio.position_sizer import FixedFractionPositionSizer, PositionSizer
from quant.risk.atr_stop import AtrStopPolicy
from quant.strategy.base import Strategy

logger = logging.getLogger(__name__)


class BacktestEngine:
    """编排单标的日线回测，不实现策略、成交或绩效公式。"""

    def __init__(
        self,
        data_feed: DataFeed,
        strategy: Strategy,
        broker: SimulatedBroker,
        portfolio: Portfolio,
        position_sizer: Optional[PositionSizer] = None,
    ) -> None:
        self.data_feed = data_feed
        self.strategy = strategy
        self.broker = broker
        self.portfolio = portfolio
        self.position_sizer = (
            position_sizer if position_sizer is not None else FixedFractionPositionSizer()
        )
        self._has_run = False

    def run(self) -> BacktestResult:
        """执行生命周期：先处理前一根信号，再估值并读取当前 Bar 产生新信号。"""
        if self._has_run:
            raise RuntimeError("BacktestEngine 实例只能运行一次；重复回测请重新创建协作者。")
        self._has_run = True
        bars = list(self.data_feed)
        self._validate_bars(bars)
        logger.info("回测开始：symbol=%s bars=%d", self.portfolio.symbol, len(bars))
        history: list[Bar] = []
        pending: list[OrderIntent] = []
        terminal_pending: list[PendingOrder] = []
        next_order_number = 1
        trades: list[Trade] = []
        order_results: list[OrderResult] = []
        equity: list[EquitySnapshot] = []
        stop_policy = AtrStopPolicy()

        for bar_index, bar in enumerate(bars):
            next_order_number, stop_attempted = self._try_execute_stop(
                bar, stop_policy, next_order_number, trades, order_results, gap_only=True,
            )

            due_intents = pending
            pending = []
            for intent in due_intents:
                # 意图来自上一根完整收盘 Bar；本根 Open 执行，避免同收盘前视。
                order_id = "order-{:06d}".format(next_order_number)
                order, rejection_reason = self._create_order(intent, bar, order_id)
                if order is None:
                    if rejection_reason:
                        order_results.append(
                            OrderResult(order_id, OrderStatus.REJECTED, rejection_reason)
                        )
                        logger.info("订单拒绝：%s %s", order_id, rejection_reason)
                        next_order_number += 1
                    continue
                next_order_number += 1
                filled = self._execute_order(
                    order, bar, stop_policy, trades, order_results,
                    intent.protective_stop_distance,
                )
                if filled and order.side == Side.BUY:
                    # Open 止损仅属于旧持仓；同日重新买入的新仓仍须检查本根 Low。
                    stop_attempted = False

            # 日线 OHLC 无法知道盘中路径；按 Low 触及止损处理，并以止损价作为参考价。
            if not stop_attempted:
                next_order_number, _ = self._try_execute_stop(
                    bar, stop_policy, next_order_number, trades, order_results,
                )

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
                if intent.symbol != bar.symbol or intent.signal_time != bar.datetime:
                    raise ValueError("策略意图必须匹配当前 Bar 的标的和信号时间。")
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

        logger.info("回测结束：trades=%d final_equity=%s", len(trades), equity[-1].portfolio_value)
        return BacktestResult(
            initial_cash=self.portfolio.initial_cash,
            trades=tuple(trades),
            equity_curve=tuple(equity),
            order_results=tuple(order_results),
            pending_orders=tuple(terminal_pending),
        )

    def _execute_order(
        self,
        order: Order,
        bar: Bar,
        stop_policy: AtrStopPolicy,
        trades: list[Trade],
        order_results: list[OrderResult],
        stop_distance: Optional[float] = None,
    ) -> bool:
        """由 Broker 成交、Portfolio 入账，并同步入账成功后的止损状态。"""
        result = self.broker.execute(order, bar)
        order_results.append(result)
        if result.status != OrderStatus.FILLED:
            logger.info("订单未成交：%s %s", result.order_id, result.reason)
            return False
        if result.trade is None:
            raise ValueError("FILLED 结果必须包含 Trade。")
        if (
            order.side == Side.BUY and stop_distance is not None
            and result.trade.price <= stop_distance
        ):
            reason = "实际买入成交价不足以形成正的保护止损价。"
            order_results[-1] = OrderResult(order.order_id, OrderStatus.REJECTED, reason)
            logger.info("成交入账拒绝：%s %s", order.order_id, reason)
            return False
        try:
            self.portfolio.apply_trade(result.trade)
        except ValueError as exc:
            order_results[-1] = OrderResult(order.order_id, OrderStatus.REJECTED, str(exc))
            logger.info("成交入账拒绝：%s %s", order.order_id, exc)
            return False
        trades.append(result.trade)
        if order.side == Side.BUY and stop_distance is not None:
            stop_policy.activate(result.trade.price, stop_distance, result.trade.signal_time)
        elif order.side == Side.SELL:
            stop_policy.clear()
        logger.debug("成交入账：%s %s quantity=%s", order.order_id, order.side, order.quantity)
        return True

    def _try_execute_stop(
        self, bar: Bar, stop_policy: AtrStopPolicy, next_order_number: int,
        trades: list[Trade], order_results: list[OrderResult], gap_only: bool = False,
    ) -> tuple[int, bool]:
        """统一止损提交路径，返回下一订单编号与是否尝试当前持仓止损。"""
        reference = stop_policy.trigger_reference(bar)
        if reference is None or (gap_only and reference != bar.open):
            return next_order_number, False
        order = self._create_stop_order(bar, stop_policy, "order-{:06d}".format(next_order_number))
        if order is None:
            return next_order_number, False
        self._execute_order(order, bar, stop_policy, trades, order_results)
        return next_order_number + 1, True

    def _create_stop_order(
        self, bar: Bar, stop_policy: AtrStopPolicy, order_id: str
    ) -> Optional[Order]:
        """把活动保护止损转成当前 Bar 的全仓止损市价单。"""
        if self.portfolio.position_quantity <= 0 or stop_policy.stop_price is None:
            return None
        signal_time = stop_policy.signal_time
        if signal_time is None or signal_time >= bar.datetime:
            return None
        return Order(
            order_id=order_id,
            symbol=bar.symbol,
            side=Side.SELL,
            quantity=self.portfolio.position_quantity,
            order_type=OrderType.STOP_MARKET,
            signal_time=signal_time,
            execution_time=bar.datetime,
            stop_price=stop_policy.stop_price,
        )

    def _create_order(
        self, intent: OrderIntent, bar: Bar, order_id: str,
    ) -> tuple[Optional[Order], str]:
        """执行时定量；无订单且原因为空表示已达到目标，否则为具体拒绝原因。"""
        if intent.signal_time >= bar.datetime:
            raise ValueError("订单只能在信号之后的 Bar 执行。")
        if intent.symbol != bar.symbol:
            raise ValueError("策略意图标的必须匹配当前 Bar。")
        current_quantity = self.portfolio.position_quantity
        side = Side.BUY if intent.target_fraction == 1 else Side.SELL
        if intent.target_fraction == 1 and current_quantity > 0:
            return None, ""
        if intent.target_fraction == 0 and current_quantity <= 0:
            return None, ""

        execution_reference = bar.open
        quantity: float
        if side == Side.BUY:
            try:
                quoted_price = self.broker.quote(side, execution_reference)
            except ValueError as exc:
                return None, str(exc)
            if (
                intent.protective_stop_distance is not None
                and quoted_price <= intent.protective_stop_distance
            ):
                return None, "保护止损距离必须小于实际买入报价。"
            # 保持比例预算的十进制口径，再由 Broker 按佣金模型检查整股可负担数量。
            equity = self.portfolio.mark_to_market(execution_reference).portfolio_value
            target_quantity = self.position_sizer.calculate_quantity(
                equity, quoted_price, intent.protective_stop_distance
            )
            equity_budget = self.position_sizer.allocation_budget(equity)
            cash_budget = min(equity_budget, Decimal(str(self.portfolio.cash)))
            try:
                affordable_quantity = self.broker.max_affordable_integer_quantity(
                    float(cash_budget), quoted_price
                )
            except ValueError as exc:
                return None, str(exc)
            quantity = min(target_quantity, affordable_quantity)
        else:
            quantity = current_quantity
        if quantity <= 0:
            return None, "当前仓位额度或含佣金可用现金不足以买入一股。"
        return Order(
            order_id=order_id,
            symbol=intent.symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.MARKET,
            signal_time=intent.signal_time,
            execution_time=bar.datetime,
        ), ""

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
