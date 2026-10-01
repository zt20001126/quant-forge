"""CSV 到策略／基准报告及可视化的端到端验证。"""

from dataclasses import replace
from pathlib import Path
from typing import Sequence, cast
from unittest.mock import patch

import matplotlib
import pytest
from examples.ma_cross_backtest import ExampleConfig, run_benchmark_example, run_example
from quant.analytics.benchmark import validate_benchmark_alignment
from quant.data.csv_feed import CSVDataFeed
from quant.visualization import plot_backtest, plot_interactive_backtest


def test_csv_comparison_preserves_strategy_and_plots_both_curves(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "date,open,high,low,close,volume\n"
        "2024-01-01,3,3,3,3,100\n"
        "2024-01-02,2,2,2,2,100\n"
        "2024-01-03,1,1,1,1,100\n"
        "2024-01-04,4,4,4,4,100\n"
        "2024-01-05,5,5,5,5,100\n"
        "2024-01-06,4,4,4,4,100\n", encoding="utf-8",
    )
    config = ExampleConfig(initial_cash=10000, short_window=2, long_window=3,
                           commission_rate=0.001, slippage_amount=0.01)
    old_result, old_metrics = run_example(path, symbol="AAA", config=config)
    original_iter = CSVDataFeed.__iter__
    with patch.object(CSVDataFeed, "__iter__", autospec=True, side_effect=original_iter) as read:
        report = run_benchmark_example(path, symbol="AAA", config=config)
        assert read.call_count == 1
    assert report.strategy_result == old_result
    assert report.strategy_metrics == old_metrics
    assert old_result.equity_curve[-1].portfolio_value == pytest.approx(7976.07006)
    assert report.benchmark_metrics.total_return == pytest.approx(4 / 3 - 1)
    assert len(report.benchmark_result.equity_curve) == 6  # 包含策略暖机期。
    bars = tuple(CSVDataFeed(path, "AAA"))
    expected = [10000 * bar.close / 3 for bar in bars]
    assert [p.equity_value for p in report.benchmark_result.equity_curve] == pytest.approx(expected)

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    figure = plot_backtest(bars, old_result, show=False, benchmark=report.benchmark_result)
    try:
        assert len(figure.axes[1].lines) == 2
        # 本图传入的是浮点序列；Matplotlib 的静态返回类型还包含标量等其他情况。
        assert list(cast(Sequence[float], figure.axes[1].lines[1].get_ydata())) == pytest.approx(
            expected
        )
    finally:
        plt.close(figure)
    interactive = plot_interactive_backtest(bars, old_result, benchmark=report.benchmark_result)
    trace = next(trace for trace in interactive.data if trace.name == "Buy & Hold (no costs)")
    assert list(trace.y) == pytest.approx(expected)
    assert list(trace.x) == [bar.datetime for bar in bars]
    assert report.strategy_result == old_result

    invalid = replace(report.benchmark_result, initial_cash=20000)
    with pytest.raises(ValueError, match="初始资金"):
        validate_benchmark_alignment(old_result, invalid)
    for plot in (plot_backtest, plot_interactive_backtest):
        with pytest.raises(ValueError):
            plot(bars, old_result, benchmark=invalid)
        with pytest.raises(ValueError):
            plot(tuple(replace(bar, symbol="BBB") for bar in bars), old_result,
                 benchmark=report.benchmark_result)
        with pytest.raises(ValueError):
            plot(bars[:-1], old_result, benchmark=report.benchmark_result)
        shifted = replace(
            old_result,
            equity_curve=(old_result.equity_curve[1], *old_result.equity_curve[1:]),
        )
        with pytest.raises(ValueError):
            plot(bars, shifted, benchmark=report.benchmark_result)


def test_one_bar_csv_produces_cash_strategy_and_intraday_benchmark(tmp_path: Path) -> None:
    path = tmp_path / "one.csv"
    path.write_text("date,open,high,low,close,volume\n2024-01-01,100,110,100,110,1\n",
                    encoding="utf-8")
    report = run_benchmark_example(path)
    assert report.strategy_result.trades == ()
    assert report.strategy_metrics.total_return == 0
    assert report.benchmark_metrics.total_return == pytest.approx(0.1)
    assert report.benchmark_metrics.sharpe_ratio == 0


def test_empty_csv_is_rejected_before_comparison(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("date,open,high,low,close,volume\n", encoding="utf-8")
    with pytest.raises(ValueError, match="不能为空"):
        run_benchmark_example(path)
