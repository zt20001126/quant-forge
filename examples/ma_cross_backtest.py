"""运行新架构的 CSV + MA Cross 日线回测示例。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Union

from quant.analytics.metrics import PerformanceMetrics, calculate_performance
from quant.broker.broker import SimulatedBroker
from quant.broker.commission import DEFAULT_COMMISSION_RATE, PercentageCommission
from quant.broker.slippage import FixedSlippage
from quant.data.csv_feed import CSVDataFeed
from quant.engine.backtest_engine import BacktestEngine
from quant.engine.models import BacktestResult
from quant.portfolio.portfolio import Portfolio
from quant.portfolio.position_sizer import FixedFractionPositionSizer
from quant.strategy.ma_cross import MACrossStrategy
from quant.visualization import plot_backtest


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
    feed = CSVDataFeed(data_path, symbol)
    broker = SimulatedBroker(
        PercentageCommission(config.commission_rate), FixedSlippage(config.slippage_amount),
    )
    portfolio = Portfolio(config.initial_cash, symbol)
    engine = BacktestEngine(
        feed, MACrossStrategy(config.short_window, config.long_window), broker, portfolio,
        FixedFractionPositionSizer(config.position_ratio),
    )
    result = engine.run()
    return result, calculate_performance(result)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    data_path = root / "data" / "stock_real.csv"
    backtest_result, metrics = run_example(data_path)
    print("Trades: {}".format(len(backtest_result.trades)))
    print("Final equity: {:.2f}".format(backtest_result.equity_curve[-1].portfolio_value))
    print("Total return: {:.2%}".format(metrics.total_return))
    print("Annualized return: {:.2%}".format(metrics.annualized_return))
    print("Max drawdown: {:.2%}".format(metrics.max_drawdown))
    print("Sharpe: {:.3f}".format(metrics.sharpe_ratio))
    # BacktestResult 不重复保存输入行情；绘图需要时再读取同一份 CSV。
    plot_backtest(list(CSVDataFeed(data_path, "DEMO")), backtest_result)
