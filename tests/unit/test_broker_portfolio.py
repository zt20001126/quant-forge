"""Broker 成交成本与 Portfolio 账户不变量测试。"""

import unittest
from datetime import datetime, timedelta

from quant.broker.broker import SimulatedBroker
from quant.broker.commission import FixedCommission, PercentageCommission
from quant.broker.slippage import FixedSlippage
from quant.core import Bar, Order, OrderStatus, OrderType, Side, Trade
from quant.portfolio.portfolio import Portfolio


class BrokerPortfolioTest(unittest.TestCase):
    def test_buy_slippage_commission_and_account_value(self) -> None:
        start = datetime(2024, 1, 1)
        next_day = start + timedelta(days=1)
        broker = SimulatedBroker(PercentageCommission(0.01), FixedSlippage(1))
        portfolio = Portfolio(1000, "AAA")
        estimated_price = broker.quote(Side.BUY, 10)
        quantity = broker.max_affordable_quantity(portfolio.cash, estimated_price)
        order = Order("o1", "AAA", Side.BUY, quantity, OrderType.MARKET, start, next_day)
        bar = Bar("AAA", next_day, 10, 12, 9, 11, 100)
        result = broker.execute(order, bar)
        self.assertEqual(result.status, OrderStatus.FILLED)
        assert result.trade is not None
        self.assertEqual(result.trade.price, 11)
        self.assertAlmostEqual(result.trade.commission, 1000 / 101)
        portfolio.apply_trade(result.trade)
        snapshot = portfolio.mark_to_market(11)
        self.assertAlmostEqual(snapshot.cash, 0)
        self.assertAlmostEqual(snapshot.average_price, 11.11)
        self.assertAlmostEqual(snapshot.portfolio_value, 1000 / 1.01)
        self.assertAlmostEqual(snapshot.portfolio_value, snapshot.cash + snapshot.market_value)

    def test_rejects_short_sale_without_changing_cash(self) -> None:
        start = datetime(2024, 1, 1)
        later = start + timedelta(days=1)
        portfolio = Portfolio(1000, "AAA")
        broker = SimulatedBroker(PercentageCommission(0), FixedSlippage(0))
        sell = Order("sell", "AAA", Side.SELL, 1, OrderType.MARKET, start, later)
        trade = broker.execute(sell, Bar("AAA", later, 10, 10, 10, 10, 1)).trade
        assert trade is not None
        with self.assertRaises(ValueError):
            portfolio.apply_trade(trade)
        self.assertEqual(portfolio.cash, 1000)

    def test_max_affordable_quantity_accounts_for_fixed_commission(self) -> None:
        broker = SimulatedBroker(FixedCommission(5), FixedSlippage(0))
        quantity = broker.max_affordable_quantity(105, 10)
        self.assertAlmostEqual(quantity, 10)

    def test_max_affordable_integer_quantity_keeps_exact_decimal_boundary(self) -> None:
        broker = SimulatedBroker(PercentageCommission(0), FixedSlippage(0))

        self.assertEqual(broker.max_affordable_integer_quantity(0.3, 0.1), 3)

    def test_max_affordable_integer_quantity_includes_fixed_commission(self) -> None:
        broker = SimulatedBroker(FixedCommission(5), FixedSlippage(0))

        self.assertEqual(broker.max_affordable_integer_quantity(105, 10), 10)

    def test_stop_market_fills_at_stop_price_when_low_touches_it(self) -> None:
        start = datetime(2024, 1, 1)
        execution = start + timedelta(days=1)
        broker = SimulatedBroker(PercentageCommission(0.01), FixedSlippage(0))
        order = Order(
            "stop",
            "AAA",
            Side.SELL,
            10,
            OrderType.STOP_MARKET,
            start,
            execution,
            stop_price=96,
        )

        result = broker.execute(order, Bar("AAA", execution, 100, 101, 95, 98, 100))

        self.assertEqual(result.status, OrderStatus.FILLED)
        assert result.trade is not None
        self.assertEqual(result.trade.price, 96)
        self.assertAlmostEqual(result.trade.commission, 9.6)

    def test_stop_market_gap_fills_at_open_and_rejects_untriggered_order(self) -> None:
        start = datetime(2024, 1, 1)
        execution = start + timedelta(days=1)
        broker = SimulatedBroker(PercentageCommission(0), FixedSlippage(0))
        order = Order(
            "stop",
            "AAA",
            Side.SELL,
            10,
            OrderType.STOP_MARKET,
            start,
            execution,
            stop_price=96,
        )

        gap_result = broker.execute(order, Bar("AAA", execution, 94, 95, 90, 92, 100))
        untouched_result = broker.execute(order, Bar("AAA", execution, 100, 101, 97, 98, 100))

        self.assertEqual(gap_result.status, OrderStatus.FILLED)
        assert gap_result.trade is not None
        self.assertEqual(gap_result.trade.price, 94)
        self.assertEqual(untouched_result.status, OrderStatus.REJECTED)

    def test_successful_sale_restores_cash_without_negative_position(self) -> None:
        start = datetime(2024, 1, 1)
        buy_time = start + timedelta(days=1)
        sell_time = start + timedelta(days=2)
        portfolio = Portfolio(1000, "AAA")
        broker = SimulatedBroker(PercentageCommission(0), FixedSlippage(0))
        buy_order = Order("buy", "AAA", Side.BUY, 100, OrderType.MARKET, start, buy_time)
        buy_trade = broker.execute(
            buy_order, Bar("AAA", buy_time, 10, 10, 10, 10, 1)
        ).trade
        assert buy_trade is not None
        portfolio.apply_trade(buy_trade)
        sell_order = Order("sell", "AAA", Side.SELL, 100, OrderType.MARKET, buy_time, sell_time)
        sell_trade = broker.execute(
            sell_order, Bar("AAA", sell_time, 10, 10, 10, 10, 1)
        ).trade
        assert sell_trade is not None
        portfolio.apply_trade(sell_trade)
        self.assertEqual(portfolio.cash, 1000)
        self.assertEqual(portfolio.position_quantity, 0)

    def test_sale_normalizes_tiny_negative_cash_within_allowed_tolerance(self) -> None:
        start = datetime(2024, 1, 1)
        buy_time = start + timedelta(days=1)
        sell_time = start + timedelta(days=2)
        portfolio = Portfolio(1, "AAA")
        portfolio.apply_trade(
            Trade("buy", "buy-order", "AAA", Side.BUY, 1, 1, 0, start, buy_time)
        )

        portfolio.apply_trade(
            Trade(
                "sell",
                "sell-order",
                "AAA",
                Side.SELL,
                1,
                1,
                1.000000005,
                buy_time,
                sell_time,
            )
        )

        self.assertEqual(portfolio.cash, 0)
        self.assertEqual(portfolio.position_quantity, 0)
        self.assertEqual(portfolio.mark_to_market(1).portfolio_value, 0)

if __name__ == "__main__":
    unittest.main()
