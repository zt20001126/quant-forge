"""无账户状态的市价订单模拟执行器。"""

from __future__ import annotations

from typing import Optional

from quant.broker.commission import CommissionModel, PercentageCommission
from quant.broker.slippage import NoSlippage, SlippageModel
from quant.core.bar import Bar
from quant.core.enums import OrderStatus, Side
from quant.core.order import Order, OrderResult
from quant.core.trade import Trade


class SimulatedBroker:
    def __init__(
        self,
        commission_model: Optional[CommissionModel] = None,
        slippage_model: Optional[SlippageModel] = None,
    ) -> None:
        self.commission_model = commission_model or PercentageCommission(0.0003)
        self.slippage_model = slippage_model or NoSlippage()

    def quote(self, side: Side, reference_price: float) -> float:
        """按配置模型返回预估成交价，供 Engine 计算可支付数量。"""
        return self.slippage_model.apply(reference_price, side)

    def max_affordable_quantity(self, cash: float, execution_price: float) -> float:
        """在给定现金与执行价下，用单调二分求含佣金的最大可买数量。

        可插拔佣金模型需满足费用非负且随数量单调不减，二分边界才成立。
        """
        if cash <= 0 or execution_price <= 0:
            return 0.0
        lower = 0.0
        upper = cash / execution_price
        for _ in range(80):
            quantity = (lower + upper) / 2
            commission = self.commission_model.calculate(execution_price, quantity)
            if commission < 0:
                raise ValueError("佣金模型不能返回负费用。")
            if execution_price * quantity + commission <= cash:
                lower = quantity
            else:
                upper = quantity
        return lower

    def execute(self, order: Order, bar: Bar) -> OrderResult:
        if order.execution_time != bar.datetime:
            return OrderResult(order.order_id, OrderStatus.REJECTED, "订单执行时间与行情时间不一致。")
        if order.symbol != bar.symbol:
            return OrderResult(order.order_id, OrderStatus.REJECTED, "订单标的与行情标的不一致。")

        reference_price = bar.open
        execution_price = self.slippage_model.apply(reference_price, order.side)
        if execution_price <= 0:
            return OrderResult(order.order_id, OrderStatus.REJECTED, "滑点导致成交价无效。")
        commission = self.commission_model.calculate(execution_price, order.quantity)
        trade = Trade(
            trade_id="trade-{}".format(order.order_id),
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            price=execution_price,
            quantity=order.quantity,
            commission=commission,
            signal_time=order.signal_time,
            execution_time=bar.datetime,
        )
        return OrderResult(order.order_id, OrderStatus.FILLED, trade=trade)
