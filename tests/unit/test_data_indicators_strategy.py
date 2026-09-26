"""Data、Indicator 和 Strategy 单元测试。"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from quant.core import Bar
from quant.data.csv_feed import CSVDataFeed
from quant.indicators.moving_average import simple_moving_average
from quant.strategy.ma_cross import MACrossStrategy


class DataIndicatorStrategyTest(unittest.TestCase):
    def test_csv_feed_sorts_and_rejects_duplicate_dates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            path.write_text(
                "date,open,high,low,close,volume\n"
                "2024-01-02,2,3,1,2,20\n"
                "2024-01-01,1,2,0.5,1,10\n",
                encoding="utf-8",
            )
            bars = list(CSVDataFeed(path, "AAA"))
            self.assertEqual([bar.datetime.day for bar in bars], [1, 2])
            path.write_text(
                "date,open,high,low,close,volume\n"
                "2024-01-01,1,2,0.5,1,10\n"
                "2024-01-01,1,2,0.5,1,10\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                list(CSVDataFeed(path, "AAA"))

    def test_csv_feed_rejects_empty_missing_and_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            for content in (
                "date,open,high,low,close,volume\n",
                "date,open,high,low,close\n2024-01-01,1,1,1,1\n",
                "date,open,high,low,close,volume\n2024-01-01,1,NaN,1,1,1\n",
                "date,open,high,low,close,volume\n2024-01-01,2,1,1,2,1\n",
                "date,open,high,low,close,volume\nnot-a-date,1,1,1,1,1\n",
            ):
                path.write_text(content, encoding="utf-8")
                with self.subTest(content=content), self.assertRaises(ValueError):
                    list(CSVDataFeed(path, "AAA"))

    def test_moving_average_has_explicit_warmup(self) -> None:
        self.assertEqual(simple_moving_average([1, 2, 3], 2), [None, 1.5, 2.5])
        with self.assertRaises(ValueError):
            simple_moving_average([1], 0)

    def test_ma_cross_emits_only_target_changes(self) -> None:
        strategy = MACrossStrategy(short_window=2, long_window=3)
        closes = [3, 2, 1, 4, 5, 6]
        bars = [
            Bar("AAA", datetime(2024, 1, 1) + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)
        ]
        emitted = []
        history = []
        for bar in bars:
            emitted.extend(strategy.on_bar(bar, history))
            history.append(bar)
        self.assertEqual([intent.target_fraction for intent in emitted], [1])
        self.assertEqual(emitted[0].signal_time, bars[3].datetime)

    def test_ma_cross_emits_exit_when_short_average_falls_below_long(self) -> None:
        strategy = MACrossStrategy(short_window=2, long_window=3)
        closes = [1, 2, 4, 3, 2]
        history = []
        emitted = []
        for index, close in enumerate(closes):
            bar = Bar(
                "AAA", datetime(2024, 2, 1) + timedelta(days=index),
                close, close, close, close, 1,
            )
            emitted.extend(strategy.on_bar(bar, history))
            history.append(bar)
        self.assertEqual([intent.target_fraction for intent in emitted], [1, 0])


if __name__ == "__main__":
    unittest.main()
