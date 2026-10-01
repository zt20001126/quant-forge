"""组装策略与基准的只读分析报告，不参与回测生命周期。"""

from dataclasses import dataclass
from typing import Sequence

from quant.analytics.benchmark import (
    BuyAndHoldBenchmarkResult,
    calculate_buy_and_hold,
    validate_benchmark_alignment,
)
from quant.analytics.metrics import (
    PerformanceMetrics,
    calculate_equity_performance,
    calculate_performance,
)
from quant.core.bar import Bar
from quant.engine.models import BacktestResult


@dataclass(frozen=True)
class BenchmarkComparison:
    """保留原始策略结果及双方指标；策略含配置成本，基准为无成本价格收益。"""

    strategy_result: BacktestResult
    strategy_metrics: PerformanceMetrics
    benchmark_result: BuyAndHoldBenchmarkResult
    benchmark_metrics: PerformanceMetrics


def compare_with_buy_and_hold(
    bars: Sequence[Bar],
    result: BacktestResult,
    annual_risk_free_rate: float = 0.0,
) -> BenchmarkComparison:
    """包含暖机期的完整区间对比，双方使用相同资金、日期与绩效公式。"""
    benchmark = calculate_buy_and_hold(bars, result.initial_cash)
    validate_benchmark_alignment(result, benchmark)
    if any(bar.close != snapshot.close_price for bar, snapshot in zip(bars, result.equity_curve)):
        raise ValueError("基准行情 Close 必须与策略快照一致。")
    return BenchmarkComparison(
        strategy_result=result,
        strategy_metrics=calculate_performance(result, annual_risk_free_rate),
        benchmark_result=benchmark,
        benchmark_metrics=calculate_equity_performance(
            benchmark.initial_cash,
            [point.equity_value for point in benchmark.equity_curve],
            annual_risk_free_rate,
        ),
    )
