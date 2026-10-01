"""运行新架构的 CSV + MA Cross 日线回测示例。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, Tuple, Union

from quant.analytics import BenchmarkComparison, compare_with_buy_and_hold
from quant.analytics.metrics import PerformanceMetrics, calculate_performance
from quant.broker.broker import SimulatedBroker
from quant.broker.commission import DEFAULT_COMMISSION_RATE, PercentageCommission
from quant.broker.slippage import FixedSlippage
from quant.core.bar import Bar
from quant.data.csv_feed import CSVDataFeed
from quant.engine.backtest_engine import BacktestEngine
from quant.engine.models import BacktestResult
from quant.portfolio.portfolio import Portfolio
from quant.portfolio.position_sizer import FixedFractionPositionSizer
from quant.strategy.ma_cross import MACrossStrategy
from quant.visualization import plot_interactive_backtest


@dataclass(frozen=True)
class ExampleConfig:
    """示例的集中参数；业务约束由对应协作者在构造时校验。"""

    initial_cash: float = 100_000
    short_window: int = 5
    long_window: int = 20
    commission_rate: float = DEFAULT_COMMISSION_RATE
    slippage_amount: float = 0.0
    position_ratio: float = 1.0


def run_example(
    data_path: Union[str, Path], symbol: str = "DEMO", config: ExampleConfig = ExampleConfig(),
) -> Tuple[BacktestResult, PerformanceMetrics]:
    """以集中配置组装 CSV、MA 策略与成本模型，返回只读结果和绩效。"""
    result = _run_bars(tuple(CSVDataFeed(data_path, symbol)), symbol, config)
    return result, calculate_performance(result)


def _run_bars(
    bars: Sequence[Bar], symbol: str, config: ExampleConfig,
) -> BacktestResult:
    """共享行情组装逻辑，避免对比时重新读取文件。"""
    broker = SimulatedBroker(
        PercentageCommission(config.commission_rate), FixedSlippage(config.slippage_amount),
    )
    portfolio = Portfolio(config.initial_cash, symbol)
    engine = BacktestEngine(
        bars, MACrossStrategy(config.short_window, config.long_window), broker, portfolio,
        FixedFractionPositionSizer(config.position_ratio),
    )
    return engine.run()


def run_benchmark_example(
    data_path: Union[str, Path], symbol: str = "DEMO", config: ExampleConfig = ExampleConfig(),
) -> BenchmarkComparison:
    """读取一次行情并返回完整区间的策略／无成本 Buy & Hold 对比。"""
    bars = tuple(CSVDataFeed(data_path, symbol))
    result = _run_bars(bars, symbol, config)
    return compare_with_buy_and_hold(bars, result)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    data_path = root / "data" / "stock_real.csv"
    bars = tuple(CSVDataFeed(data_path, "DEMO"))
    backtest_result = _run_bars(bars, "DEMO", ExampleConfig())
    comparison = compare_with_buy_and_hold(bars, backtest_result)
    metrics = comparison.strategy_metrics
    print("Trades: {}".format(len(backtest_result.trades)))
    print("Final equity: {:.2f}".format(backtest_result.equity_curve[-1].portfolio_value))
    print("Total return: {:.2%}".format(metrics.total_return))
    print("Annualized return: {:.2%}".format(metrics.annualized_return))
    print("Max drawdown: {:.2%}".format(metrics.max_drawdown))
    print("Sharpe: {:.3f}".format(metrics.sharpe_ratio))
    print("Benchmark: Buy & Hold，首日 Open 满仓、小数股、无佣金/滑点；策略含配置成本。")
    print("指标                  Strategy      Buy & Hold")
    for label, strategy_value, benchmark_value in (
        ("Total return", metrics.total_return, comparison.benchmark_metrics.total_return),
        ("Annualized return", metrics.annualized_return,
         comparison.benchmark_metrics.annualized_return),
        ("Max drawdown", metrics.max_drawdown, comparison.benchmark_metrics.max_drawdown),
    ):
        print(f"{label:20} {strategy_value:12.2%} {benchmark_value:12.2%}")
    print(f"{'Sharpe':20} {metrics.sharpe_ratio:12.3f} "
          f"{comparison.benchmark_metrics.sharpe_ratio:12.3f}")
    # 使用回测时固定的同一份行情，避免重读 CSV 后发生输入错配。
    # Plotly 默认在浏览器中打开交互图；静态绘图接口仍保留给其他调用者。
    figure = plot_interactive_backtest(
        bars, backtest_result, benchmark=comparison.benchmark_result,
    )
    figure.show()
