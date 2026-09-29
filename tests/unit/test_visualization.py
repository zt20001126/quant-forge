"""回测图表内容与展示边界测试。"""

import unittest
from datetime import datetime, timedelta

import matplotlib
from quant.core.bar import Bar
from quant.core.enums import Side
from quant.core.trade import Trade
from quant.engine.models import BacktestResult, EquitySnapshot
from quant.visualization import plot_backtest, plot_interactive_backtest


class VisualizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # 测试使用无窗口后端，避免绘图测试弹出桌面窗口。
        matplotlib.use("Agg")

    def test_plot_shows_close_trades_and_equity_without_daily_direction_dots(self) -> None:
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
            self.assertEqual(len(price_axis.collections), 2)
            self.assertEqual(len(price_axis.lines), 1)
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

    def test_interactive_plot_has_three_linked_panels_daily_hover_and_optional_series(self) -> None:
        start = datetime(2024, 1, 1)
        bars = [
            Bar("AAA", start + timedelta(days=index), 10 + index, 12 + index,
                9 + index, 11 + index, 100 + index)
            for index in range(3)
        ]
        trade = Trade("t1", "o1", "AAA", Side.BUY, 12, 5, 0.5,
                      start, bars[1].datetime)
        result = BacktestResult(
            100, (trade,),
            tuple(EquitySnapshot(bar.datetime, 40, "AAA", 5, bar.close, 5 * bar.close, value)
                  for bar, value in zip(bars, (100, 95, 110))),
            (), (),
        )
        figure = plot_interactive_backtest(
            bars, result, indicators={"MA5": (None, 10.5, 11.5)},
            stop_prices=(None, 8, 9),
        )
        names = {trace.name for trace in figure.data}
        self.assertTrue({"Close", "MA5", "Stop loss", "BUY", "Portfolio Equity", "Drawdown"}
                        <= names)
        close = next(trace for trace in figure.data if trace.name == "Close")
        self.assertEqual(list(close.customdata[0]), [10, 12, 9, 11, 100])
        trade_trace = next(trace for trace in figure.data if trace.name == "BUY")
        self.assertIn("Commission", trade_trace.hovertemplate)
        self.assertIn("Slippage", trade_trace.hovertemplate)
        self.assertEqual(figure.layout.xaxis.matches, "x")
        self.assertTrue(figure.layout.xaxis3.rangeslider.visible)
        drawdowns = list(next(trace for trace in figure.data if trace.name == "Drawdown").y)
        self.assertAlmostEqual(drawdowns[0], 0)
        self.assertAlmostEqual(drawdowns[1], -0.05)
        self.assertAlmostEqual(drawdowns[2], 0)

    def test_interactive_plot_rejects_mismatched_optional_data(self) -> None:
        bar = Bar("AAA", datetime(2024, 1, 1), 10, 11, 9, 10, 100)
        result = BacktestResult(100, (),
            (EquitySnapshot(bar.datetime, 100, "AAA", 0, 10, 0, 100),), (), ())
        with self.assertRaises(ValueError):
            plot_interactive_backtest([bar], result, indicators={"MA5": []})


if __name__ == "__main__":
    unittest.main()
