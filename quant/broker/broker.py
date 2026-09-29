"""无账户状态的市价订单模拟执行器。"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal
from typing import Optional

from quant.broker.commission import DEFAULT_COMMISSION_RATE, CommissionModel, PercentageCommission
from quant.broker.slippage import NoSlippage, SlippageModel
from quant.core.bar import Bar
from quant.core.enums import OrderStatus, OrderType, Side
from quant.core.order import Order, OrderResult
from quant.core.trade import Trade
from quant.core.validation import validate_non_negative_finite, validate_positive_finite

FRACTIONAL_QUANTITY_SEARCH_STEPS = 80


class SimulatedBroker:
    """执行订单与成本报价，不保存现金或持仓。"""

    def __init__(
        self,
        commission_model: Optional[CommissionModel] = None,
        slippage_model: Optional[SlippageModel] = None,
    ) -> None:
        self.commission_model = (
            commission_model if commission_model is not None
            else PercentageCommission(DEFAULT_COMMISSION_RATE)
        )
        self.slippage_model = slippage_model if slippage_model is not None else NoSlippage()

    def quote(self, side: Side, reference_price: float) -> float:
        """按配置模型返回预估成交价，供 Engine 计算可支付数量。"""
        validate_positive_finite(reference_price, "reference_price")
        if not isinstance(side, Side):
            raise ValueError("side 必须是 Side 枚举。")
        price = self.slippage_model.apply(reference_price, side)
        validate_positive_finite(price, "execution_price")
        return price

    def max_affordable_quantity(self, cash: float, execution_price: float) -> float:
        """在给定现金与执行价下，用单调二分求含佣金的最大可买数量。

        可插拔佣金模型需满足费用非负且随数量单调不减，二分边界才成立。
        这里的佣金调用仅用于报价；最终实际费用由 execute 生成的 Trade 记录并入账。
        """
        validate_non_negative_finite(cash, "cash")
        validate_positive_finite(execution_price, "execution_price")
        if cash == 0:
            return 0.0
        lower = 0.0
        upper = cash / execution_price
        validate_positive_finite(upper, "quantity_upper_bound")
        for _ in range(FRACTIONAL_QUANTITY_SEARCH_STEPS):
            quantity = (lower + upper) / 2
            commission = self._calculate_commission(execution_price, quantity)
            if execution_price * quantity + commission <= cash:
                lower = quantity
            else:
                upper = quantity
        return lower

    def max_affordable_integer_quantity(self, cash: float, execution_price: float) -> int:
        """返回按整股计、包含佣金且不超预算的最大买入数量。

        以十进制金额比较整股候选值，避免二分逼近或二进制浮点误差将
        刚好可负担的整股错误向下截断。佣金模型仍须非负且随数量单调不减。
        """
        validate_non_negative_finite(cash, "cash")
        validate_positive_finite(execution_price, "execution_price")
        if cash == 0:
            return 0
        cash_value = Decimal(str(cash))
        price_value = Decimal(str(execution_price))

        maximum_without_commission = int(
            (cash_value / price_value).to_integral_value(rounding=ROUND_FLOOR)
        )
        affordable = 0
        unaffordable = maximum_without_commission + 1
        while affordable + 1 < unaffordable:
            quantity = (affordable + unaffordable) // 2
            commission = self._calculate_commission(execution_price, quantity)
            commission_value = Decimal(str(commission))

            total_cost = price_value * quantity + commission_value
            if total_cost <= cash_value:
                affordable = quantity
            else:
                unaffordable = quantity
        return affordable

    def execute(self, order: Order, bar: Bar) -> OrderResult:
        """市价单以 Open、止损单以跳空 Open 或止损价为参考，再应用成交成本。"""
        if order.execution_time != bar.datetime:
            return OrderResult(
                order.order_id, OrderStatus.REJECTED, "订单执行时间与行情时间不一致。"
            )
        if order.symbol != bar.symbol:
            return OrderResult(order.order_id, OrderStatus.REJECTED, "订单标的与行情标的不一致。")

        reference_price = bar.open
        if order.order_type == OrderType.STOP_MARKET:
            assert order.stop_price is not None
            if bar.open <= order.stop_price:
                reference_price = bar.open
            elif bar.low <= order.stop_price:
                reference_price = order.stop_price
            else:
                return OrderResult(
                    order.order_id,
                    OrderStatus.REJECTED,
                    "止损价未被当前 Bar 触发。",
                )
        try:
            execution_price = self.quote(order.side, reference_price)
            commission = self._calculate_commission(execution_price, order.quantity)
        except ValueError as exc:
            # 非法模型输出是明确的未成交结果，不能构造成非法 Trade 或默默当作零费率。
            return OrderResult(order.order_id, OrderStatus.REJECTED, str(exc))
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

    def _calculate_commission(self, price: float, quantity: float) -> float:
        """报价和真实成交共同验证成本模型的有限非负费用。"""
        commission = self.commission_model.calculate(price, quantity)
        validate_non_negative_finite(commission, "commission")
        return commission
