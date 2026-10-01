"""单标的 Buy & Hold 理论价格基准，不模拟订单或拥有交易账户。"""

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from quant.core.bar import Bar
from quant.core.validation import (
    validate_datetime,
    validate_positive_finite,
    validate_symbol,
)
from quant.engine.models import BacktestResult


@dataclass(frozen=True)
class BenchmarkEquityPoint:
    """基准的日终理论权益，不表示真实账户快照。"""

    timestamp: datetime
    equity_value: float

    def __post_init__(self) -> None:
        validate_datetime(self.timestamp, "timestamp")
        validate_positive_finite(self.equity_value, "equity_value")


@dataclass(frozen=True)
class BuyAndHoldBenchmarkResult:
    """首根 Open 全额投入、小数股、零佣金滑点，末日 Close 估值的只读基准。"""

    symbol: str
    initial_cash: float
    entry_price: float
    equity_curve: tuple[BenchmarkEquityPoint, ...]

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_positive_finite(self.initial_cash, "initial_cash")
        validate_positive_finite(self.entry_price, "entry_price")
        if not self.equity_curve:
            raise ValueError("基准权益曲线不能为空。")
        for previous, current in zip(self.equity_curve, self.equity_curve[1:]):
            if current.timestamp <= previous.timestamp:
                raise ValueError("基准时间必须严格递增且无重复。")


def calculate_buy_and_hold(
    bars: Sequence[Bar], initial_cash: float,
) -> BuyAndHoldBenchmarkResult:
    """按同一行情生成基准；入场假设在区间开始前确定，不使用首日 Close 决策。"""
    validate_positive_finite(initial_cash, "initial_cash")
    if not bars:
        raise ValueError("基准行情不能为空。")
    symbol = bars[0].symbol
    entry_price = bars[0].open
    points: list[BenchmarkEquityPoint] = []
    previous_time = None
    for bar in bars:
        if bar.symbol != symbol:
            raise ValueError("基准仅支持同一标的。")
        if previous_time is not None and bar.datetime <= previous_time:
            raise ValueError("基准行情时间必须严格递增且无重复。")
        # 理论满仓不受整股约束；首日 Open→Close 收益必须保留，不另加初值点。
        equity = initial_cash * (bar.close / entry_price)
        points.append(BenchmarkEquityPoint(bar.datetime, equity))
        previous_time = bar.datetime
    return BuyAndHoldBenchmarkResult(symbol, initial_cash, entry_price, tuple(points))


def validate_benchmark_alignment(
    result: BacktestResult, benchmark: BuyAndHoldBenchmarkResult,
) -> None:
    """拒绝资金、标的或逐日时间不一致的比较；不截短或填补数据。"""
    if result.initial_cash != benchmark.initial_cash:
        raise ValueError("策略与基准初始资金必须一致。")
    if len(result.equity_curve) != len(benchmark.equity_curve):
        raise ValueError("策略与基准权益曲线长度必须一致。")
    for snapshot, point in zip(result.equity_curve, benchmark.equity_curve):
        if snapshot.timestamp != point.timestamp:
            raise ValueError("策略与基准时间必须逐日一致。")
        if snapshot.symbol != benchmark.symbol:
            raise ValueError("策略与基准标的必须一致。")
