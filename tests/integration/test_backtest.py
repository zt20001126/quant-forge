"""CSV 到绩效摘要的新框架集成测试。"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from quant.analytics.metrics import calculate_performance
from quant.broker.broker import SimulatedBroker
from quant.broker.commission import PercentageCommission
from quant.broker.slippage import FixedSlippage
from quant.data.csv_feed import CSVDataFeed
from quant.engine.backtest_engine import BacktestEngine
from quant.portfolio.portfolio import Portfolio
from quant.strategy.ma_cross import MACrossStrategy


class EndToEndBacktestTest(unittest.TestCase):
    def test_csv_to_trades_equity_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            rows = [
                ("2024-01-01", 3), ("2024-01-02", 2), ("2024-01-03", 1),
                ("2024-01-04", 4), ("2024-01-05", 5), ("2024-01-06", 4),
            ]
            path.write_text(
                "date,open,high,low,close,volume\n" + "".join(
                    "{},{},{},{},{},100\n".format(date, price, price, price, price)
                    for date, price in rows
                ),
                encoding="utf-8",
            )
            portfolio = Portfolio(10_000, "AAA")
            engine = BacktestEngine(
                CSVDataFeed(path, "AAA"),
                MACrossStrategy(2, 3),
                SimulatedBroker(PercentageCommission(0.001), FixedSlippage(0.01)),
                portfolio,
            )
            result = engine.run()
            metrics = calculate_performance(result)
            self.assertEqual(len(result.equity_curve), len(rows))
            self.assertTrue(result.trades)
            self.assertTrue(-1 <= metrics.total_return)
            self.assertAlmostEqual(
                result.equity_curve[-1].portfolio_value,
                result.equity_curve[-1].cash + result.equity_curve[-1].market_value,
            )


if __name__ == "__main__":
    unittest.main()
