"""Broker 成交成本与 Portfolio 账户不变量测试。"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from quant.broker.broker import SimulatedBroker
from quant.broker.commission import PercentageCommission
from quant.broker.slippage import FixedSlippage
from quant.core import Bar, Order, OrderStatus, OrderType, Side
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
        portfolio.apply_trade(result.trade)
        snapshot = portfolio.mark_to_market(11)
        self.assertAlmostEqual(snapshot.cash, 0)
        self.assertAlmostEqual(snapshot.portfolio_value, snapshot.cash + snapshot.market_value)

    def test_rejects_short_sale_and_duplicate_trade(self) -> None:
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
        from quant.broker.commission import FixedCommission

        broker = SimulatedBroker(FixedCommission(5), FixedSlippage(0))
        quantity = broker.max_affordable_quantity(105, 10)
        self.assertAlmostEqual(quantity, 10)

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


if __name__ == "__main__":
    unittest.main()
