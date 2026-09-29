"""CSV 到绩效摘要的新框架集成测试。"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Sequence

from quant.analytics.metrics import calculate_performance
from quant.broker.broker import SimulatedBroker
from quant.broker.commission import PercentageCommission
from quant.broker.slippage import FixedSlippage
from quant.core import Bar
from quant.core.enums import Side
from quant.core.order import OrderIntent
from quant.data.csv_feed import CSVDataFeed
from quant.engine.backtest_engine import BacktestEngine
from quant.portfolio.portfolio import Portfolio
from quant.portfolio.position_sizer import RiskBasedPositionSizer
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
            self.assertEqual(len(result.trades), 1)
            trade = result.trades[0]
            self.assertEqual(trade.side, Side.BUY)
            self.assertEqual(trade.quantity, 1994)
            self.assertAlmostEqual(trade.price, 5.01)
            self.assertAlmostEqual(trade.commission, 9.98994)
            self.assertEqual(trade.signal_time, datetime(2024, 1, 4))
            self.assertEqual(trade.execution_time, datetime(2024, 1, 5))
            self.assertAlmostEqual(result.equity_curve[-1].cash, 0.07006)
            self.assertAlmostEqual(result.equity_curve[-1].portfolio_value, 7976.07006)
            self.assertAlmostEqual(metrics.total_return, -0.202392994)
            self.assertAlmostEqual(
                result.equity_curve[-1].portfolio_value,
                result.equity_curve[-1].cash + result.equity_curve[-1].market_value,
            )

    def test_risk_sized_atr_stop_closes_through_broker_and_portfolio(self) -> None:
        start = datetime(2024, 1, 1)
        bars = [
            Bar("AAA", start, 100, 101, 99, 100, 100),
            Bar("AAA", start + timedelta(days=1), 100, 102, 97, 101, 100),
            Bar("AAA", start + timedelta(days=2), 100, 101, 95, 98, 100),
        ]

        class Feed:
            def __iter__(self) -> Iterator[Bar]:
                return iter(bars)

        class ProtectedEntryStrategy:
            def on_bar(self, bar: Bar, history: Sequence[Bar]) -> list[OrderIntent]:
                if not history:
                    return [OrderIntent(bar.symbol, 1, bar.datetime, protective_stop_distance=4)]
                return []

        portfolio = Portfolio(10_000, "AAA")
        engine = BacktestEngine(
            Feed(),
            ProtectedEntryStrategy(),
            SimulatedBroker(PercentageCommission(0.001), FixedSlippage(0)),
            portfolio,
            RiskBasedPositionSizer(risk_fraction=0.01),
        )

        result = engine.run()

        self.assertEqual([trade.side for trade in result.trades], [Side.BUY, Side.SELL])
        self.assertEqual([trade.quantity for trade in result.trades], [25, 25])
        self.assertEqual([trade.price for trade in result.trades], [100, 96])
        self.assertAlmostEqual(result.trades[0].commission, 2.5)
        self.assertAlmostEqual(result.trades[1].commission, 2.4)
        self.assertEqual(portfolio.position_quantity, 0)
        self.assertAlmostEqual(portfolio.cash, 9_895.1)
        self.assertAlmostEqual(result.equity_curve[-1].portfolio_value, 9_895.1)


if __name__ == "__main__":
    unittest.main()
