"""订单意图与提交给 Broker 的订单。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from quant.core.enums import OrderStatus, OrderType, Side
from quant.core.trade import Trade
from quant.core.validation import validate_datetime, validate_positive_finite, validate_symbol


@dataclass(frozen=True)
class OrderIntent:
    """策略方向意图：0 为空仓，1 为多头；实际投入比例由仓位器决定。"""

    symbol: str
    target_fraction: float
    signal_time: datetime
    protective_stop_distance: Optional[float] = None

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_datetime(self.signal_time, "signal_time")
        if isinstance(self.target_fraction, bool) or self.target_fraction not in (0, 1):
            raise ValueError("V0.1 目标仓位只能是 0 或 1。")
        if self.protective_stop_distance is not None:
            validate_positive_finite(self.protective_stop_distance, "protective_stop_distance")
            if self.target_fraction != 1:
                raise ValueError("保护止损距离只允许附加到买入意图。")


@dataclass(frozen=True)
class Order:
    """已确定数量和执行时间、等待 Broker 执行的订单。"""

    order_id: str
    symbol: str
    side: Side
    quantity: float
    order_type: OrderType
    signal_time: datetime
    execution_time: datetime
    stop_price: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, str) or not self.order_id.strip():
            raise ValueError("order_id 不能为空。")
        validate_symbol(self.symbol)
        if not isinstance(self.side, Side):
            raise ValueError("side 必须是 Side 枚举。")
        if not isinstance(self.order_type, OrderType):
            raise ValueError("order_type 必须是 OrderType 枚举。")
        validate_positive_finite(self.quantity, "quantity")
        validate_datetime(self.signal_time, "signal_time")
        validate_datetime(self.execution_time, "execution_time")
        if self.execution_time <= self.signal_time:
            raise ValueError("订单执行时间必须晚于信号时间。")
        if self.order_type == OrderType.MARKET and self.stop_price is not None:
            raise ValueError("市价单不能携带 stop_price。")
        if self.order_type == OrderType.STOP_MARKET:
            if self.side != Side.SELL:
                raise ValueError("V0.1 止损市价单仅支持卖出。")
            if self.stop_price is None:
                raise ValueError("止损市价单必须提供 stop_price。")
            validate_positive_finite(self.stop_price, "stop_price")


@dataclass(frozen=True)
class OrderResult:
    """订单执行状态；只有 FILLED 结果应包含 Trade。"""

    order_id: str
    status: OrderStatus
    reason: str = ""
    trade: Optional[Trade] = None

    def __post_init__(self) -> None:
        if not isinstance(self.order_id, str) or not self.order_id.strip():
            raise ValueError("order_id 不能为空。")
        if not isinstance(self.status, OrderStatus):
            raise ValueError("status 必须是 OrderStatus 枚举。")
        if not isinstance(self.reason, str):
            raise ValueError("reason 必须是字符串。")
        if self.status == OrderStatus.FILLED:
            if not isinstance(self.trade, Trade):
                raise ValueError("FILLED 结果必须包含 Trade。")
            if self.trade.order_id != self.order_id:
                raise ValueError("Trade 必须关联同一订单。")
        elif self.trade is not None:
            raise ValueError("未成交结果不能包含 Trade。")
