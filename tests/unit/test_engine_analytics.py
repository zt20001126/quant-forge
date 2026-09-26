"""回测生命周期与绩效公式测试。"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from quant.analytics.metrics import calculate_performance
from quant.broker.broker import SimulatedBroker
from quant.broker.commission import PercentageCommission
from quant.broker.slippage import NoSlippage
from quant.data.csv_feed import CSVDataFeed
from quant.engine.backtest_engine import BacktestEngine
from quant.engine.models import BacktestResult, EquitySnapshot
from quant.portfolio.portfolio import Portfolio
from quant.strategy.ma_cross import MACrossStrategy


class EngineAnalyticsTest(unittest.TestCase):
    def test_signal_executes_next_bar_open_and_last_signal_expires(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            path.write_text(
                "date,open,high,low,close,volume\n"
                "2024-01-01,3,3,3,3,1\n"
                "2024-01-02,2,2,2,2,1\n"
                "2024-01-03,1,1,1,1,1\n"
                "2024-01-04,4,4,4,4,1\n"
                "2024-01-05,10,10,1,1,1\n"
                "2024-01-06,1,1,1,1,1\n",
                encoding="utf-8",
            )
            feed = CSVDataFeed(path, "AAA")
            portfolio = Portfolio(1000, "AAA")
            engine = BacktestEngine(
                feed,
                MACrossStrategy(2, 3),
                SimulatedBroker(PercentageCommission(0), NoSlippage()),
                portfolio,
            )
            result = engine.run()
            self.assertEqual(len(result.trades), 1)
            trade = result.trades[0]
            self.assertEqual(trade.signal_time, datetime(2024, 1, 4))
            self.assertEqual(trade.execution_time, datetime(2024, 1, 5))
            self.assertEqual(trade.price, 10)
            self.assertEqual(result.equity_curve[-1].timestamp, datetime(2024, 1, 6))
            self.assertTrue(result.pending_orders)
            self.assertEqual(result.pending_orders[0].status, "EXPIRED_NO_NEXT_BAR")
            with self.assertRaises(RuntimeError):
                engine.run()

    def test_performance_uses_initial_cash_as_baseline(self) -> None:
        timestamps = [datetime(2024, 1, 1) + timedelta(days=index) for index in range(3)]
        result = BacktestResult(
            100,
            (),
            tuple(
                EquitySnapshot(timestamp, 100, "AAA", 0, 10, 0, 100)
                for timestamp in timestamps
            ),
            (),
            (),
        )
        metrics = calculate_performance(result)
        self.assertEqual(metrics.total_return, 0)
        self.assertEqual(metrics.max_drawdown, 0)
        self.assertEqual(metrics.sharpe_ratio, 0)


if __name__ == "__main__":
    unittest.main()
