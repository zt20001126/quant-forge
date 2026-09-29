"""固定比例仓位计算及其在交易流程中的行为测试。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from typing import Iterator, List, Sequence

from quant.broker.broker import SimulatedBroker
from quant.broker.commission import PercentageCommission
from quant.broker.slippage import NoSlippage
from quant.core import Bar, Side
from quant.core.order import OrderIntent
from quant.engine.backtest_engine import BacktestEngine
from quant.portfolio.portfolio import Portfolio
from quant.portfolio.position_sizer import FixedFractionPositionSizer, RiskBasedPositionSizer


class BuyThenSellStrategy:
    """测试用策略：先表达买入意图，再表达清仓意图。"""

    def on_bar(self, bar: Bar, history: Sequence[Bar]) -> List[OrderIntent]:
        if not history:
            return [OrderIntent(bar.symbol, 1, bar.datetime)]
        if len(history) == 2:
            return [OrderIntent(bar.symbol, 0, bar.datetime)]
        return []


class FixedFractionPositionSizerTest(unittest.TestCase):
    def test_calculates_requested_examples(self) -> None:
        self.assertEqual(FixedFractionPositionSizer(0.2).calculate_quantity(100_000, 50), 400)
        self.assertEqual(FixedFractionPositionSizer(0.5).calculate_quantity(100_000, 50), 1000)
        self.assertEqual(FixedFractionPositionSizer(0.1).calculate_quantity(100_000, 50), 200)

    def test_invalid_equity_or_price_produces_no_quantity(self) -> None:
        sizer = FixedFractionPositionSizer(0.2)
        self.assertEqual(sizer.calculate_quantity(0, 50), 0)
        self.assertEqual(sizer.calculate_quantity(-10, 50), 0)
        self.assertEqual(sizer.calculate_quantity(100_000, 0), 0)
        self.assertEqual(sizer.calculate_quantity(100_000, -1), 0)

    def test_position_ratio_must_be_in_open_closed_unit_interval(self) -> None:
        for ratio in (0, -0.1, 1.01, float("inf"), float("nan"), True):
            with self.subTest(ratio=ratio), self.assertRaises(ValueError):
                FixedFractionPositionSizer(ratio)

    def test_fractional_share_is_rounded_down_without_float_overspend(self) -> None:
        sizer = FixedFractionPositionSizer(0.2)
        self.assertEqual(sizer.calculate_quantity(100, 30), 0)
        self.assertEqual(sizer.calculate_quantity(100, 6), 3)

    def test_buy_uses_sizer_and_sell_uses_existing_holding(self) -> None:
        start = datetime(2024, 1, 1)
        bars = [
            Bar("AAA", start + timedelta(days=index), 50, 50, 50, 50, 100)
            for index in range(4)
        ]

        class Feed:
            def __iter__(self) -> Iterator[Bar]:
                return iter(bars)

        portfolio = Portfolio(100_000, "AAA")
        engine = BacktestEngine(
            Feed(),
            BuyThenSellStrategy(),
            SimulatedBroker(PercentageCommission(0), NoSlippage()),
            portfolio,
            FixedFractionPositionSizer(0.2),
        )
        result = engine.run()
        self.assertEqual([trade.side for trade in result.trades], [Side.BUY, Side.SELL])
        self.assertEqual(result.trades[0].quantity, 400)
        self.assertEqual(result.trades[1].quantity, 400)
        self.assertEqual(portfolio.position_quantity, 0)

    def test_engine_preserves_decimal_position_ratio_at_integer_boundary(self) -> None:
        start = datetime(2024, 1, 1)
        bars = [
            Bar("AAA", start + timedelta(days=index), 1, 1, 1, 1, 100)
            for index in range(2)
        ]

        class Feed:
            def __iter__(self) -> Iterator[Bar]:
                return iter(bars)

        engine = BacktestEngine(
            Feed(),
            BuyThenSellStrategy(),
            SimulatedBroker(PercentageCommission(0), NoSlippage()),
            Portfolio(100, "AAA"),
            FixedFractionPositionSizer(0.29),
        )

        result = engine.run()

        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].quantity, 29)

    def test_risk_based_sizer_uses_loss_budget_divided_by_stop_distance(self) -> None:
        sizer = RiskBasedPositionSizer(risk_fraction=0.01)

        self.assertEqual(sizer.calculate_quantity(10_000, 100, stop_distance=4), 25)
        self.assertEqual(sizer.allocation_budget(10_000), 10_000)

    def test_risk_based_sizer_rejects_missing_or_invalid_stop_distance(self) -> None:
        sizer = RiskBasedPositionSizer(risk_fraction=0.01)

        for stop_distance in (None, 0, -1, float("inf"), float("nan")):
            with self.subTest(stop_distance=stop_distance), self.assertRaises(ValueError):
                sizer.calculate_quantity(10_000, 100, stop_distance)

    def test_risk_fraction_must_be_in_open_closed_unit_interval(self) -> None:
        for risk_fraction in (0, -0.1, 1.01, float("inf"), float("nan"), True):
            with self.subTest(risk_fraction=risk_fraction), self.assertRaises(ValueError):
                RiskBasedPositionSizer(risk_fraction)

    def test_buy_is_limited_by_available_cash_and_commission(self) -> None:
        sizer = FixedFractionPositionSizer(1.0)
        quantity = sizer.calculate_quantity(1_000, 10)
        broker = SimulatedBroker(PercentageCommission(0.1), NoSlippage())
        affordable = broker.max_affordable_quantity(100, 10)
        self.assertEqual(min(quantity, int(affordable)), 9)

    def test_engine_does_not_submit_buy_when_budget_cannot_buy_one_share(self) -> None:
        start = datetime(2024, 1, 1)
        bars = [
            Bar("AAA", start + timedelta(days=index), 50, 50, 50, 50, 100)
            for index in range(2)
        ]

        class Feed:
            def __iter__(self) -> Iterator[Bar]:
                return iter(bars)

        engine = BacktestEngine(
            Feed(),
            BuyThenSellStrategy(),
            SimulatedBroker(PercentageCommission(0), NoSlippage()),
            Portfolio(100, "AAA"),
            FixedFractionPositionSizer(0.2),
        )
        result = engine.run()
        self.assertEqual(result.trades, ())
        self.assertEqual(result.order_results[0].status.value, "REJECTED")


if __name__ == "__main__":
    unittest.main()
