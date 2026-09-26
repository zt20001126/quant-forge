"""已成交交易记录。"""

from dataclasses import dataclass
from datetime import datetime

from quant.core.enums import Side
from quant.core.validation import (
    validate_datetime,
    validate_non_negative_finite,
    validate_positive_finite,
    validate_symbol,
)


@dataclass(frozen=True)
class Trade:
    trade_id: str
    order_id: str
    symbol: str
    side: Side
    price: float
    quantity: float
    commission: float
    signal_time: datetime
    execution_time: datetime

    def __post_init__(self) -> None:
        if not self.trade_id or not self.order_id:
            raise ValueError("trade_id 和 order_id 不能为空。")
        validate_symbol(self.symbol)
        if not isinstance(self.side, Side):
            raise ValueError("side 必须是 Side 枚举。")
        validate_positive_finite(self.price, "price")
        validate_positive_finite(self.quantity, "quantity")
        validate_non_negative_finite(self.commission, "commission")
        validate_datetime(self.signal_time, "signal_time")
        validate_datetime(self.execution_time, "execution_time")
        if self.execution_time <= self.signal_time:
            raise ValueError("成交时间必须晚于信号时间。")
