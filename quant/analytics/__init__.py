"""回测结果分析。"""

from quant.analytics.benchmark import (
    BenchmarkEquityPoint,
    BuyAndHoldBenchmarkResult,
    calculate_buy_and_hold,
)
from quant.analytics.metrics import (
    PerformanceMetrics,
    calculate_equity_performance,
    calculate_performance,
)
from quant.analytics.report import BenchmarkComparison, compare_with_buy_and_hold

__all__ = [
    "BenchmarkComparison", "BenchmarkEquityPoint", "BuyAndHoldBenchmarkResult",
    "PerformanceMetrics", "calculate_buy_and_hold", "calculate_equity_performance",
    "calculate_performance", "compare_with_buy_and_hold",
]
