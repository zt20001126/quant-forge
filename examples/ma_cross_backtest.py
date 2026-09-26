"""运行新架构的 CSV + MA Cross 日线回测示例。"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple, Union

from quant.analytics.metrics import PerformanceMetrics, calculate_performance
from quant.broker.broker import SimulatedBroker
from quant.broker.commission import PercentageCommission
from quant.broker.slippage import NoSlippage
from quant.data.csv_feed import CSVDataFeed
from quant.engine.backtest_engine import BacktestEngine
from quant.engine.models import BacktestResult
from quant.portfolio.portfolio import Portfolio
from quant.strategy.ma_cross import MACrossStrategy


def run_example(
    data_path: Union[str, Path], symbol: str = "DEMO"
) -> Tuple[BacktestResult, PerformanceMetrics]:
    feed = CSVDataFeed(data_path, symbol)
    broker = SimulatedBroker(PercentageCommission(0.0003), NoSlippage())
    portfolio = Portfolio(100_000, symbol)
    engine = BacktestEngine(feed, MACrossStrategy(5, 20), broker, portfolio)
    result = engine.run()
    return result, calculate_performance(result)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    backtest_result, metrics = run_example(root / "data" / "stock_real.csv")
    print("Trades: {}".format(len(backtest_result.trades)))
    print("Final equity: {:.2f}".format(backtest_result.equity_curve[-1].portfolio_value))
    print("Total return: {:.2%}".format(metrics.total_return))
    print("Annualized return: {:.2%}".format(metrics.annualized_return))
    print("Max drawdown: {:.2%}".format(metrics.max_drawdown))
    print("Sharpe: {:.3f}".format(metrics.sharpe_ratio))
