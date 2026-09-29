"""回测图表内容与展示边界测试。"""

import unittest
from datetime import datetime, timedelta

import matplotlib
from quant.core.bar import Bar
from quant.core.enums import Side
from quant.core.trade import Trade
from quant.engine.models import BacktestResult, EquitySnapshot
from quant.visualization import plot_backtest


class VisualizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # 测试使用无窗口后端，避免绘图测试弹出桌面窗口。
        matplotlib.use("Agg")

    def test_plot_shows_daily_direction_trades_and_equity(self) -> None:
        start = datetime(2024, 1, 1)
        bars = [
            Bar("AAA", start, 10, 10, 10, 10, 100),
            Bar("AAA", start + timedelta(days=1), 12, 12, 12, 12, 100),
            Bar("AAA", start + timedelta(days=2), 11, 11, 11, 11, 100),
        ]
        trades = (
            Trade("t1", "o1", "AAA", Side.BUY, 12, 5, 0, start, bars[1].datetime),
            Trade("t2", "o2", "AAA", Side.SELL, 11, 5, 0, bars[1].datetime, bars[2].datetime),
        )
        result = BacktestResult(
            initial_cash=100,
            trades=trades,
            equity_curve=tuple(
                EquitySnapshot(bar.datetime, 100, "AAA", 0, bar.close, 0, value)
                for bar, value in zip(bars, (100, 110, 105))
            ),
            order_results=(),
            pending_orders=(),
        )

        figure = plot_backtest(bars, result, show=False)
        try:
            price_axis, equity_axis = figure.axes
            self.assertIn(
                price_axis.get_title(),
                ("回测：价格与成交信号", "Backtest: Price and Trades"),
            )
            self.assertIn(
                {collection.get_label() for collection in price_axis.collections},
                (
                    {"上涨日", "下跌日", "买入成交", "卖出成交"},
                    {"Up day", "Down day", "Buy", "Sell"},
                ),
            )
            self.assertIn(equity_axis.lines[0].get_label(), ("组合权益", "Portfolio value"))
            self.assertEqual(list(equity_axis.lines[0].get_ydata()), [100, 110, 105])
        finally:
            from matplotlib import pyplot as plt

            plt.close(figure)

    def test_plot_uses_custom_title_and_releases_figure(self) -> None:
        from matplotlib import pyplot as plt

        bar = Bar("AAA", datetime(2024, 1, 1), 10, 10, 10, 10, 100)
        result = BacktestResult(100, (), (
            EquitySnapshot(bar.datetime, 100, "AAA", 0, 10, 0, 100),
        ), (), ())
        figure = plot_backtest([bar], result, show=False, title="Acceptance")
        try:
            self.assertEqual(figure.axes[0].get_title(), "Acceptance")
        finally:
            plt.close(figure)
        self.assertNotIn(figure.number, plt.get_fignums())

    def test_plot_rejects_missing_bars_or_equity(self) -> None:
        with self.assertRaises(ValueError):
            plot_backtest([], BacktestResult(100, (), (), (), ()), show=False)


if __name__ == "__main__":
    unittest.main()
