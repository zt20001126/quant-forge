"""Core Domain Model 的不变量测试。"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from quant.core import Bar, Order, OrderStatus, OrderType, OrderIntent, Position, Side, Trade


class CoreDomainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.signal_time = datetime(2024, 1, 2)
        self.execution_time = self.signal_time + timedelta(days=1)

    def test_bar_validates_ohlc_and_volume(self) -> None:
        bar = Bar("AAA", self.signal_time, 10, 12, 9, 11, 100)
        self.assertEqual(bar.close, 11)
        with self.assertRaises(ValueError):
            Bar("AAA", self.signal_time, 10, 9, 8, 11, 100)

    def test_intent_is_target_fraction_and_v01_is_long_only(self) -> None:
        self.assertEqual(OrderIntent("AAA", 1, self.signal_time).target_fraction, 1)
        with self.assertRaises(ValueError):
            OrderIntent("AAA", -1, self.signal_time)

    def test_order_and_trade_preserve_signal_and_execution_times(self) -> None:
        order = Order("o1", "AAA", Side.BUY, 2, OrderType.MARKET, self.signal_time, self.execution_time)
        trade = Trade("t1", order.order_id, "AAA", Side.BUY, 10, 2, 0.01, order.signal_time, order.execution_time)
        self.assertGreater(trade.execution_time, trade.signal_time)
        self.assertEqual(OrderStatus.NEW.value, "NEW")
        with self.assertRaises(ValueError):
            Order("o2", "AAA", Side.BUY, 2, OrderType.MARKET, self.signal_time, self.signal_time)

    def test_position_market_value(self) -> None:
        self.assertEqual(Position("AAA", 3, 10).market_value(12), 36)


if __name__ == "__main__":
    unittest.main()
