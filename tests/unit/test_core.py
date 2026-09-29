"""Core Domain Model 的不变量测试。"""

import unittest
from datetime import datetime, timedelta

from quant.core import Bar, Order, OrderIntent, OrderStatus, OrderType, Position, Side, Trade


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
        protected_entry = OrderIntent("AAA", 1, self.signal_time, protective_stop_distance=4)
        self.assertEqual(protected_entry.protective_stop_distance, 4)
        with self.assertRaises(ValueError):
            OrderIntent("AAA", -1, self.signal_time)
        for stop_distance in (0, -1, float("inf"), float("nan")):
            with self.subTest(stop_distance=stop_distance), self.assertRaises(ValueError):
                OrderIntent("AAA", 1, self.signal_time, stop_distance)
        with self.assertRaises(ValueError):
            OrderIntent("AAA", 0, self.signal_time, protective_stop_distance=4)

    def test_order_and_trade_preserve_signal_and_execution_times(self) -> None:
        order = Order(
            "o1", "AAA", Side.BUY, 2, OrderType.MARKET, self.signal_time, self.execution_time
        )
        trade = Trade(
            "t1", order.order_id, "AAA", Side.BUY, 10, 2, 0.01,
            order.signal_time, order.execution_time,
        )
        self.assertGreater(trade.execution_time, trade.signal_time)
        self.assertEqual(OrderStatus.NEW.value, "NEW")
        with self.assertRaises(ValueError):
            Order("o2", "AAA", Side.BUY, 2, OrderType.MARKET, self.signal_time, self.signal_time)

    def test_stop_market_order_requires_sell_side_and_positive_stop_price(self) -> None:
        order = Order(
            "stop",
            "AAA",
            Side.SELL,
            2,
            OrderType.STOP_MARKET,
            self.signal_time,
            self.execution_time,
            stop_price=9,
        )
        self.assertEqual(order.stop_price, 9)
        with self.assertRaises(ValueError):
            Order(
                "bad-stop",
                "AAA",
                Side.BUY,
                2,
                OrderType.STOP_MARKET,
                self.signal_time,
                self.execution_time,
                stop_price=9,
            )
        with self.assertRaises(ValueError):
            Order(
                "missing-stop",
                "AAA",
                Side.SELL,
                2,
                OrderType.STOP_MARKET,
                self.signal_time,
                self.execution_time,
            )

    def test_position_market_value(self) -> None:
        self.assertEqual(Position("AAA", 3, 10).market_value(12), 36)


if __name__ == "__main__":
    unittest.main()
