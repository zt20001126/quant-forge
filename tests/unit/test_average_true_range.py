"""True Range 与 Wilder ATR 的计算和边界测试。"""

import unittest
from datetime import datetime, timedelta

from quant.core.bar import Bar
from quant.indicators.average_true_range import average_true_range, true_range


class AverageTrueRangeTest(unittest.TestCase):
    def setUp(self) -> None:
        start = datetime(2024, 1, 1)
        self.bars = [
            Bar("AAA", start, 10, 12, 10, 11, 100),
            Bar("AAA", start + timedelta(days=1), 13, 14, 12, 13, 100),
            Bar("AAA", start + timedelta(days=2), 10, 11, 8, 9, 100),
        ]

    def test_true_range_includes_gaps_from_previous_close(self) -> None:
        self.assertEqual(true_range(self.bars), [2, 3, 5])
        self.assertEqual(true_range([]), [])
        self.assertEqual(true_range(self.bars[:1]), [2])

    def test_atr_uses_sma_seed_then_wilder_smoothing(self) -> None:
        values = average_true_range(self.bars, period=2)

        self.assertEqual(values[:2], [None, 2.5])
        self.assertAlmostEqual(values[2], 3.75)

    def test_period_one_matches_true_range_for_every_bar(self) -> None:
        self.assertEqual(average_true_range(self.bars, period=1), [2, 3, 5])

    def test_empty_or_short_history_has_explicit_warmup(self) -> None:
        self.assertEqual(average_true_range([], period=2), [])
        self.assertEqual(average_true_range(self.bars[:1], period=2), [None])
        self.assertEqual(average_true_range(self.bars, period=4), [None, None, None])

    def test_future_bars_do_not_change_atr_for_an_existing_prefix(self) -> None:
        prefix_atr = average_true_range(self.bars[:2], period=2)[-1]
        full_history_atr = average_true_range(self.bars, period=2)[1]

        self.assertEqual(prefix_atr, full_history_atr)

    def test_period_must_be_a_positive_integer(self) -> None:
        for period in (0, -1, True, 1.5):
            with self.subTest(period=period), self.assertRaises(ValueError):
                average_true_range(self.bars, period=period)

    def test_bars_must_be_ordered_and_belong_to_one_symbol(self) -> None:
        with self.assertRaises(ValueError):
            true_range([self.bars[1], self.bars[0]])

        other_symbol = Bar(
            "BBB", self.bars[1].datetime, 13, 14, 12, 13, 100
        )
        with self.assertRaises(ValueError):
            true_range([self.bars[0], other_symbol])

        duplicate_time = Bar(
            "AAA", self.bars[0].datetime, 13, 14, 12, 13, 100
        )
        with self.assertRaises(ValueError):
            true_range([self.bars[0], duplicate_time])


if __name__ == "__main__":
    unittest.main()
