"""保护止损与合法零波动行情的回测回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

import pytest
from examples.ma_cross_backtest import ExampleConfig, run_example
from quant.broker.broker import SimulatedBroker
from quant.broker.commission import PercentageCommission
from quant.broker.slippage import NoSlippage
from quant.core import Bar, Order, OrderIntent, OrderResult, OrderStatus, OrderType, Side
from quant.engine.backtest_engine import BacktestEngine
from quant.portfolio.portfolio import Portfolio
from quant.strategy.ma_cross import MACrossStrategy


class RepeatedProtectedBuyStrategy:
    """每根收盘重新表达多头目标，用于验证止损后新仓的保护。"""

    def on_bar(self, bar: Bar, history: Sequence[Bar]) -> list[OrderIntent]:
        return [OrderIntent(bar.symbol, 1, bar.datetime, 4)]


def test_zero_atr_delays_entry_until_positive_distance_is_available() -> None:
    start = datetime(2024, 1, 1)
    bars = [
        Bar("AAA", start + timedelta(days=i), price, price, price, price, 100)
        for i, price in enumerate([10, 10, 12, 12, 13, 13])
    ]
    result = BacktestEngine(
        bars, MACrossStrategy(2, 4, atr_period=1, atr_multiplier=1),
        SimulatedBroker(PercentageCommission(0), NoSlippage()), Portfolio(1000, "AAA"),
    ).run()
    assert len(result.trades) == 1
    assert result.trades[0].signal_time == bars[4].datetime
    assert result.trades[0].execution_time == bars[5].datetime
    assert result.trades[0].side == Side.BUY


def test_gap_stop_then_reentry_checks_new_position_intraday_stop() -> None:
    start = datetime(2024, 1, 1)
    bars = [
        Bar("AAA", start, 100, 101, 99, 100, 100),
        Bar("AAA", start + timedelta(days=1), 100, 101, 99, 100, 100),
        Bar("AAA", start + timedelta(days=2), 90, 91, 80, 85, 100),
    ]
    portfolio = Portfolio(1000, "AAA")
    result = BacktestEngine(
        bars, RepeatedProtectedBuyStrategy(),
        SimulatedBroker(PercentageCommission(0), NoSlippage()), portfolio,
    ).run()
    assert [trade.side for trade in result.trades] == [Side.BUY, Side.SELL, Side.BUY, Side.SELL]
    assert [trade.price for trade in result.trades] == [100, 90, 90, 86]
    assert portfolio.position_quantity == 0
    assert portfolio.cash == 860
    assert result.equity_curve[-1].portfolio_value == 860


def test_existing_position_is_not_stopped_twice_after_rejected_gap_sale() -> None:
    start = datetime(2024, 1, 1)
    bars = [
        Bar("AAA", start, 100, 101, 99, 100, 100),
        Bar("AAA", start + timedelta(days=1), 100, 101, 99, 100, 100),
        Bar("AAA", start + timedelta(days=2), 90, 91, 80, 85, 100),
    ]

    class RejectGapBroker(SimulatedBroker):
        def execute(self, order: Order, bar: Bar) -> OrderResult:
            if order.order_type == OrderType.STOP_MARKET:
                return OrderResult(order.order_id, OrderStatus.REJECTED, "测试拒绝止损")
            return super().execute(order, bar)

    result = BacktestEngine(
        bars, RepeatedProtectedBuyStrategy(),
        RejectGapBroker(PercentageCommission(0), NoSlippage()), Portfolio(1000, "AAA"),
    ).run()
    assert len(result.order_results) == 2
    assert result.equity_curve[-1].quantity == 10


@pytest.mark.parametrize("distance,reason", [(200, "止损距离"), (4, "不足以买入一股")])
def test_buy_rejection_keeps_specific_reason(distance: float, reason: str) -> None:
    class EntryStrategy:
        def on_bar(self, bar: Bar, history: Sequence[Bar]) -> list[OrderIntent]:
            return [OrderIntent(bar.symbol, 1, bar.datetime, distance)] if not history else []

    start = datetime(2024, 1, 1)
    bars = [Bar("AAA", start + timedelta(days=i), 100, 101, 99, 100, 100) for i in range(2)]
    portfolio = Portfolio(1, "AAA")
    result = BacktestEngine(
        bars, EntryStrategy(), SimulatedBroker(PercentageCommission(0), NoSlippage()), portfolio,
    ).run()
    assert not result.trades
    assert reason in result.order_results[0].reason
    assert portfolio.cash == 1
    assert portfolio.position_quantity == 0


@pytest.mark.parametrize("invalid", ["symbol", "past_time", "future_time"])
def test_invalid_signal_is_rejected_even_on_terminal_bar(invalid: str) -> None:
    start = datetime(2024, 1, 1)

    class InvalidStrategy:
        def on_bar(self, bar: Bar, history: Sequence[Bar]) -> list[OrderIntent]:
            symbol = "BBB" if invalid == "symbol" else bar.symbol
            timestamp = bar.datetime + timedelta(days=1 if invalid == "future_time" else -1)
            return [OrderIntent(symbol, 1, timestamp)]

    with pytest.raises(ValueError, match="当前 Bar"):
        BacktestEngine(
            [Bar("AAA", start, 100, 101, 99, 100, 100)], InvalidStrategy(),
            SimulatedBroker(), Portfolio(1000, "AAA"),
        ).run()


def test_configurable_example_uses_requested_cash_costs_and_position(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "date,open,high,low,close,volume\n"
        "2024-01-01,10,10,10,10,100\n"
        "2024-01-02,10,10,10,10,100\n"
        "2024-01-03,12,12,12,12,100\n"
        "2024-01-04,12,12,12,12,100\n", encoding="utf-8",
    )
    config = ExampleConfig(
        1000, 2, 3, commission_rate=0.01, slippage_amount=0.1, position_ratio=0.5,
    )
    result, metrics = run_example(path, "AAA", config)
    assert result.initial_cash == 1000
    assert len(result.trades) == 1
    assert result.trades[0].quantity == 40
    assert result.trades[0].price == pytest.approx(12.1)
    assert result.equity_curve[-1].cash == pytest.approx(511.16)
    assert metrics.total_return == pytest.approx(-0.00884)


def test_changed_execution_quote_cannot_commit_unprotectable_position() -> None:
    class ChangingSlippage:
        def __init__(self) -> None:
            self.calls = 0

        def apply(self, price: float, side: Side) -> float:
            self.calls += 1
            return 100 if self.calls == 1 else 2

    start = datetime(2024, 1, 1)
    bars = [Bar("AAA", start + timedelta(days=i), 100, 101, 99, 100, 100) for i in range(2)]
    portfolio = Portfolio(1000, "AAA")
    result = BacktestEngine(
        bars, RepeatedProtectedBuyStrategy(),
        SimulatedBroker(PercentageCommission(0), ChangingSlippage()), portfolio,
    ).run()
    assert not result.trades
    assert "实际买入成交价" in result.order_results[0].reason
    assert portfolio.cash == 1000
    assert portfolio.position_quantity == 0
