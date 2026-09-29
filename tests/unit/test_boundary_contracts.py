"""公开边界的领域不变量、非法数值与配置一致性回归测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

import pytest
from quant.analytics.metrics import calculate_performance
from quant.broker.broker import SimulatedBroker
from quant.broker.commission import FixedCommission, PercentageCommission
from quant.broker.slippage import FixedSlippage, NoSlippage, PercentageSlippage
from quant.core import Bar, Order, OrderResult, OrderStatus, OrderType, Position, Side, Trade
from quant.engine.models import BacktestResult, EquitySnapshot
from quant.portfolio.portfolio import Portfolio
from quant.portfolio.position_sizer import FixedFractionPositionSizer, RiskBasedPositionSizer
from quant.risk.atr_stop import AtrStopPolicy
from quant.strategy.ma_cross import MACrossStrategy


def test_oversell_within_old_tolerance_is_rejected_without_cash_creation() -> None:
    start = datetime(2024, 1, 1)
    portfolio = Portfolio(100, "AAA")
    portfolio.apply_trade(
        Trade("b", "b", "AAA", Side.BUY, 100, 1, 0, start, start + timedelta(days=1))
    )
    before = portfolio.mark_to_market(100)
    with pytest.raises(ValueError, match="卖出数量"):
        portfolio.apply_trade(Trade(
            "s", "s", "AAA", Side.SELL, 1e9, 1.000000005, 0,
            start + timedelta(days=1), start + timedelta(days=2),
        ))
    assert portfolio.mark_to_market(100) == before


def test_small_residual_position_is_preserved() -> None:
    start = datetime(2024, 1, 1)
    portfolio = Portfolio(100, "AAA")
    portfolio.apply_trade(
        Trade("b", "b", "AAA", Side.BUY, 100, 1, 0, start, start + timedelta(days=1))
    )
    portfolio.apply_trade(Trade(
        "s", "s", "AAA", Side.SELL, 100, 1 - 5e-9, 0,
        start + timedelta(days=1), start + timedelta(days=2),
    ))
    assert portfolio.position_quantity > 0
    assert portfolio.mark_to_market(1e9).market_value == pytest.approx(5, abs=1e-6)


@pytest.mark.parametrize("window", [1.5, float("nan"), float("inf"), True])
def test_invalid_strategy_window_is_rejected_at_construction(window: float) -> None:
    with pytest.raises(ValueError, match="窗口"):
        # 故意突破静态类型约束，验证公开入口的运行时保护。
        MACrossStrategy(cast(int, window), 3)


@pytest.mark.parametrize("distance", [-4, 0, float("nan"), float("inf"), True])
def test_stop_activation_rejects_invalid_distance_atomically(distance: float) -> None:
    stop = AtrStopPolicy()
    start = datetime(2024, 1, 1)
    stop.activate(100, 4, start)
    with pytest.raises(ValueError):
        stop.activate(100, distance, start)
    assert stop.stop_price == 96
    assert stop.signal_time == start


def test_position_rejects_nonfinite_realized_pnl() -> None:
    with pytest.raises(ValueError):
        Position("AAA", realized_pnl=float("nan"))


def test_filled_order_result_requires_trade() -> None:
    with pytest.raises(ValueError, match="Trade"):
        OrderResult("order", OrderStatus.FILLED)


def test_result_rejects_trade_on_rejected_order_or_wrong_order_id() -> None:
    start = datetime(2024, 1, 1)
    trade = Trade("trade", "order", "AAA", Side.BUY, 10, 1, 0, start, start + timedelta(days=1))
    with pytest.raises(ValueError):
        OrderResult("order", OrderStatus.REJECTED, trade=trade)
    with pytest.raises(ValueError):
        OrderResult("other-order", OrderStatus.FILLED, trade=trade)
    assert OrderResult("order", OrderStatus.FILLED, trade=trade).trade == trade


def test_sizer_configuration_is_readonly_and_matches_calculation() -> None:
    fixed = FixedFractionPositionSizer(0.2)
    risk = RiskBasedPositionSizer(0.01)
    with pytest.raises(AttributeError):
        setattr(fixed, "position_ratio", 0.5)
    with pytest.raises(AttributeError):
        setattr(risk, "risk_fraction", 0.5)
    assert fixed.calculate_quantity(1000, 10) == 20
    assert risk.calculate_quantity(1000, 10, 1) == 10


def test_false_valued_commission_model_is_preserved() -> None:
    class ZeroCommission:
        def __bool__(self) -> bool:
            return False

        def calculate(self, price: float, quantity: float) -> float:
            return 0

    model = ZeroCommission()
    broker = SimulatedBroker(commission_model=model)
    assert broker.commission_model is model
    assert broker.max_affordable_integer_quantity(100, 10) == 10


@pytest.mark.parametrize("cash", [float("nan"), float("inf"), -1])
def test_both_affordability_methods_reject_invalid_cash(cash: float) -> None:
    broker = SimulatedBroker(PercentageCommission(0))
    with pytest.raises(ValueError):
        broker.max_affordable_quantity(cash, 10)
    with pytest.raises(ValueError):
        broker.max_affordable_integer_quantity(cash, 10)


def test_affordability_does_not_treat_nan_commission_as_zero_budget() -> None:
    class InvalidCommission:
        def calculate(self, price: float, quantity: float) -> float:
            return float("nan")

    broker = SimulatedBroker(InvalidCommission())
    with pytest.raises(ValueError):
        broker.max_affordable_quantity(100, 10)
    with pytest.raises(ValueError):
        broker.max_affordable_integer_quantity(100, 10)


def test_annualization_overflow_raises_explained_value_error() -> None:
    result = BacktestResult(100, (), (
        EquitySnapshot(datetime(2024, 1, 1), 2000, "AAA", 0, 10, 0, 2000),
    ), (), ())
    with pytest.raises(ValueError, match="年化"):
        calculate_performance(result)


@pytest.mark.parametrize("price", [0, -1, float("nan"), float("inf")])
def test_affordability_rejects_invalid_execution_price(price: float) -> None:
    broker = SimulatedBroker(PercentageCommission(0))
    with pytest.raises(ValueError):
        broker.max_affordable_quantity(100, price)
    with pytest.raises(ValueError):
        broker.max_affordable_integer_quantity(100, price)


def test_zero_cash_produces_zero_affordable_quantity() -> None:
    broker = SimulatedBroker(PercentageCommission(0))
    assert broker.max_affordable_quantity(0, 10) == 0
    assert broker.max_affordable_integer_quantity(0, 10) == 0


@pytest.mark.parametrize("invalid", [-1, float("nan"), float("inf"), True])
def test_cost_model_constructors_reject_invalid_values(invalid: float) -> None:
    for constructor in (PercentageCommission, FixedCommission, FixedSlippage, PercentageSlippage):
        with pytest.raises(ValueError):
            constructor(invalid)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), 0, -1])
def test_invalid_slippage_quote_becomes_explicit_rejected_order(invalid: float) -> None:
    class InvalidSlippage:
        def apply(self, price: float, side: Side) -> float:
            return invalid

    start = datetime(2024, 1, 1)
    bar = Bar("AAA", start + timedelta(days=1), 10, 10, 10, 10, 100)
    order = Order("order", "AAA", Side.BUY, 1, OrderType.MARKET, start, bar.datetime)
    broker = SimulatedBroker(PercentageCommission(0), InvalidSlippage())
    with pytest.raises(ValueError):
        broker.quote(Side.BUY, 10)
    result = broker.execute(order, bar)
    assert result.status == OrderStatus.REJECTED
    assert result.reason
    assert result.trade is None


def test_invalid_commission_becomes_explicit_rejected_order() -> None:
    class InvalidCommission:
        def calculate(self, price: float, quantity: float) -> float:
            return float("nan")

    start = datetime(2024, 1, 1)
    bar = Bar("AAA", start + timedelta(days=1), 10, 10, 10, 10, 100)
    order = Order("order", "AAA", Side.SELL, 1, OrderType.MARKET, start, bar.datetime)
    result = SimulatedBroker(InvalidCommission()).execute(order, bar)
    assert result.status == OrderStatus.REJECTED
    assert "commission" in result.reason


def test_false_valued_slippage_model_is_preserved() -> None:
    class FalseNoSlippage(NoSlippage):
        def __bool__(self) -> bool:
            return False

    model = FalseNoSlippage()
    broker = SimulatedBroker(slippage_model=model)
    assert broker.slippage_model is model
    assert broker.quote(Side.BUY, 10) == 10


def test_invalid_stop_entry_and_time_do_not_replace_active_stop() -> None:
    start = datetime(2024, 1, 1)
    stop = AtrStopPolicy()
    stop.activate(100, 4, start)
    with pytest.raises(ValueError):
        stop.activate(float("nan"), 4, start)
    with pytest.raises(TypeError):
        stop.activate(100, 4, cast(datetime, None))
    assert stop.stop_price == 96
    assert stop.signal_time == start


def test_partial_sale_retains_cost_basis_and_total_assets() -> None:
    start = datetime(2024, 1, 1)
    portfolio = Portfolio(1000, "AAA")
    portfolio.apply_trade(
        Trade("b", "b", "AAA", Side.BUY, 10, 10, 1, start, start + timedelta(days=1))
    )
    portfolio.apply_trade(Trade(
        "s", "s", "AAA", Side.SELL, 12, 4, 0.48,
        start + timedelta(days=1), start + timedelta(days=2),
    ))
    snapshot = portfolio.mark_to_market(12)
    assert snapshot.quantity == 6
    assert snapshot.average_price == pytest.approx(10.1)
    assert snapshot.cash == pytest.approx(946.52)
    assert snapshot.portfolio_value == pytest.approx(1018.52)


def test_overflowing_trade_is_rejected_before_account_mutation() -> None:
    start = datetime(2024, 1, 1)
    portfolio = Portfolio(1000, "AAA")
    before = portfolio.mark_to_market(10)
    with pytest.raises(ValueError):
        portfolio.apply_trade(Trade(
            "b", "b", "AAA", Side.BUY, 1e308, 10, 0, start, start + timedelta(days=1),
        ))
    assert portfolio.mark_to_market(10) == before
