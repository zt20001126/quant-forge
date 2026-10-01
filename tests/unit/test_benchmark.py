"""Buy & Hold 价格基准、时间对齐及共用绩效公式测试。"""

from dataclasses import FrozenInstanceError, astuple, replace
from datetime import datetime, timedelta
from typing import Sequence

import pytest
from quant.analytics import (
    calculate_buy_and_hold,
    calculate_equity_performance,
    calculate_performance,
    compare_with_buy_and_hold,
)
from quant.core.bar import Bar
from quant.engine.models import BacktestResult, EquitySnapshot


def sample_bars() -> tuple[Bar, ...]:
    return tuple(
        Bar("AAA", datetime(2024, 1, 1) + timedelta(days=index),
            100, max(100, close), min(100, close), close, 10)
        for index, close in enumerate((110, 99, 121))
    )


def cash_result(bars: Sequence[Bar], cash: float = 1000) -> BacktestResult:
    return BacktestResult(cash, (), tuple(
        EquitySnapshot(bar.datetime, cash, bar.symbol, 0, bar.close, 0, cash)
        for bar in bars
    ), (), ())


def test_equity_and_four_metrics_match_manual_values() -> None:
    bars = sample_bars()
    report = compare_with_buy_and_hold(bars, cash_result(bars))
    assert [p.equity_value for p in report.benchmark_result.equity_curve] == pytest.approx(
        [1100, 990, 1210]
    )
    assert [p.timestamp for p in report.benchmark_result.equity_curve] == [
        bar.datetime for bar in bars
    ]
    metrics = report.benchmark_metrics
    assert metrics.total_return == pytest.approx(0.21)
    assert metrics.annualized_return == pytest.approx(1.21**84 - 1)
    assert metrics.max_drawdown == pytest.approx(-0.1)
    # 三期收益为 1/10、-1/10、2/9；均值 2/27，样本方差 643/24300。
    assert metrics.sharpe_ratio == pytest.approx((2 / 27) / (643 / 24300)**0.5 * 252**0.5)
    assert report.strategy_metrics.total_return == 0


def test_fractional_shares_and_capital_scaling() -> None:
    bars = sample_bars()
    small = compare_with_buy_and_hold(bars, cash_result(bars, 1))
    large = compare_with_buy_and_hold(bars, cash_result(bars, 1000))
    assert [p.equity_value for p in small.benchmark_result.equity_curve] == pytest.approx(
        [1.1, 0.99, 1.21]
    )
    assert astuple(small.benchmark_metrics) == pytest.approx(astuple(large.benchmark_metrics))


@pytest.mark.parametrize("rate", [0.0, 0.03])
def test_metric_wrapper_matches_shared_entry_and_risk_free_rate(rate: float) -> None:
    bars = sample_bars()
    values = [90.0, 120.0, 96.0]
    result = replace(cash_result(bars, 100), equity_curve=tuple(
        replace(snapshot, portfolio_value=value)
        for snapshot, value in zip(cash_result(bars, 100).equity_curve, values)
    ))
    assert calculate_performance(result, rate) == calculate_equity_performance(100, values, rate)
    report = compare_with_buy_and_hold(bars, cash_result(bars), rate)
    assert report.benchmark_metrics == calculate_equity_performance(1000, [1100, 990, 1210], rate)


def test_single_day_preserves_open_to_close_loss() -> None:
    bar = Bar("AAA", datetime(2024, 1, 1), 100, 100, 90, 90, 1)
    metrics = compare_with_buy_and_hold([bar], cash_result([bar])).benchmark_metrics
    assert metrics.total_return == pytest.approx(-0.1)
    assert metrics.max_drawdown == pytest.approx(-0.1)
    assert metrics.annualized_return == pytest.approx(0.9**252 - 1)
    assert metrics.sharpe_ratio == 0


def test_flat_prices_have_zero_metrics() -> None:
    bars = tuple(replace(bar, close=100) for bar in sample_bars())
    metrics = compare_with_buy_and_hold(bars, cash_result(bars)).benchmark_metrics
    assert (metrics.total_return, metrics.annualized_return,
            metrics.max_drawdown, metrics.sharpe_ratio) == (0, 0, 0, 0)


def test_future_prices_do_not_change_equity_prefix() -> None:
    bars = sample_bars()
    prefix = calculate_buy_and_hold(bars[:2], 1000)
    full = calculate_buy_and_hold(bars, 1000)
    assert prefix.equity_curve == full.equity_curve[:2]
    changed = calculate_buy_and_hold((*bars[:2], replace(bars[2], close=100)), 1000)
    assert prefix.equity_curve == changed.equity_curve[:2]


@pytest.mark.parametrize("cash", [0, -1, float("nan"), float("inf"), True])
def test_invalid_capital_is_rejected(cash: float) -> None:
    with pytest.raises(ValueError):
        calculate_buy_and_hold(sample_bars(), cash)


def test_empty_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="不能为空"):
        calculate_buy_and_hold([], 1000)
    with pytest.raises(ValueError):
        compare_with_buy_and_hold(sample_bars(), cash_result([]))
    with pytest.raises(ValueError):
        calculate_equity_performance(1000, [])


def test_invalid_bar_order_duplicates_and_symbols_are_rejected() -> None:
    bars = sample_bars()
    for invalid in (bars[::-1], (bars[0], bars[0]), (bars[0], replace(bars[1], symbol="BBB"))):
        with pytest.raises(ValueError):
            calculate_buy_and_hold(invalid, 1000)


@pytest.mark.parametrize("field", ["timestamp", "symbol", "close_price"])
def test_same_length_mismatched_results_are_rejected(field: str) -> None:
    bars = sample_bars()
    result = cash_result(bars)
    first = result.equity_curve[0]
    if field == "timestamp":
        first = replace(first, timestamp=first.timestamp - timedelta(days=1))
    elif field == "symbol":
        first = replace(first, symbol="BBB")
    else:
        first = replace(first, close_price=100)
    with pytest.raises(ValueError):
        compare_with_buy_and_hold(
            bars, replace(result, equity_curve=(first, *result.equity_curve[1:])),
        )


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_equity_is_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        calculate_equity_performance(1000, [value])


def test_equity_and_annualization_overflow_are_rejected() -> None:
    bar = Bar("AAA", datetime(2024, 1, 1), 1, 2, 1, 2, 1)
    with pytest.raises(ValueError):
        calculate_buy_and_hold([bar], 1e308)
    with pytest.raises(ValueError, match="年化"):
        calculate_equity_performance(100, [2000])


def test_comparison_keeps_original_result_unchanged() -> None:
    bars = sample_bars()
    result = cash_result(bars)
    before = replace(result)
    report = compare_with_buy_and_hold(bars, result)
    assert report.strategy_result is result
    assert result == before


def test_report_and_curve_are_readonly() -> None:
    bars = sample_bars()
    report = compare_with_buy_and_hold(bars, cash_result(bars))
    with pytest.raises(FrozenInstanceError):
        setattr(report.benchmark_result, "entry_price", 1)
    with pytest.raises(FrozenInstanceError):
        setattr(report.benchmark_result.equity_curve[0], "equity_value", 1)


@pytest.mark.parametrize("rate", [-1.0, float("nan"), float("inf")])
def test_invalid_risk_free_rate_is_rejected(rate: float) -> None:
    bars = sample_bars()
    with pytest.raises(ValueError):
        compare_with_buy_and_hold(bars, cash_result(bars), rate)
