"""回测结果及逐日资产快照。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from quant.core.enums import Side
from quant.core.order import OrderResult
from quant.core.trade import Trade


@dataclass(frozen=True)
class EquitySnapshot:
    timestamp: datetime
    cash: float
    symbol: str
    quantity: Optional[float]
    close_price: float
    market_value: float
    portfolio_value: float


@dataclass(frozen=True)
class PendingOrder:
    order_id: str
    symbol: str
    side: Side
    quantity: float
    signal_time: datetime
    status: str


@dataclass(frozen=True)
class BacktestResult:
    initial_cash: float
    trades: Tuple[Trade, ...]
    equity_curve: Tuple[EquitySnapshot, ...]
    order_results: Tuple[OrderResult, ...]
    pending_orders: Tuple[PendingOrder, ...]
