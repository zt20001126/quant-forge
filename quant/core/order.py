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
    """策略目标仓位意图；V0.1 仅接受 0（空仓）或 1（满仓）。"""

    symbol: str
    target_fraction: float
    signal_time: datetime

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_datetime(self.signal_time, "signal_time")
        if isinstance(self.target_fraction, bool) or self.target_fraction not in (0, 1):
            raise ValueError("V0.1 目标仓位只能是 0 或 1。")


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

    def __post_init__(self) -> None:
        if not self.order_id:
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
        if self.order_type != OrderType.MARKET:
            raise ValueError("V0.1 仅支持市价单。")


@dataclass(frozen=True)
class OrderResult:
    """订单执行状态；只有 FILLED 结果应包含 Trade。"""

    order_id: str
    status: OrderStatus
    reason: str = ""
    trade: Optional[Trade] = None

    def __post_init__(self) -> None:
        if not self.order_id:
            raise ValueError("order_id 不能为空。")
        if not isinstance(self.status, OrderStatus):
            raise ValueError("status 必须是 OrderStatus 枚举。")
