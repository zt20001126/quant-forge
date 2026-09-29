"""回测结果及逐日资产快照。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, Tuple

from quant.core.enums import Side
from quant.core.order import OrderResult
from quant.core.trade import Trade


@dataclass(frozen=True)
class EquitySnapshot:
    """单个估值时点的现金、市值和组合总资产。"""

    timestamp: datetime
    cash: float
    symbol: str
    quantity: float
    close_price: float
    market_value: float
    portfolio_value: float


@dataclass(frozen=True)
class PendingOrder:
    """缺少后续执行 Bar 的终态意图；买入数量尚不能确定。"""

    order_id: str
    symbol: str
    side: Side
    quantity: Optional[float]
    signal_time: datetime
    status: Literal["EXPIRED_NO_NEXT_BAR"]


@dataclass(frozen=True)
class BacktestResult:
    """供 Analytics 与示例消费的回测产物，不包含运行中可变账户状态。"""

    initial_cash: float
    trades: Tuple[Trade, ...]
    equity_curve: Tuple[EquitySnapshot, ...]
    order_results: Tuple[OrderResult, ...]
    pending_orders: Tuple[PendingOrder, ...]
