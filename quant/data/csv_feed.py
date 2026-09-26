"""单标的日线 CSV 行情适配器。"""

from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Union

from quant.core.bar import Bar


class CSVDataFeed:
    """将 CSV 日线校验并转换为按时间排序的领域 Bar。"""

    REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")

    def __init__(self, file_path: Union[str, Path], symbol: str) -> None:
        self.file_path = Path(file_path)
        self.symbol = symbol

    def __iter__(self) -> Iterator[Bar]:
        """完整校验输入后再产出行情，避免部分坏数据进入回测。"""
        if not self.file_path.is_file():
            raise FileNotFoundError("未找到行情文件：{}".format(self.file_path))

        bars: list[Bar] = []
        with self.file_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError("CSV 文件没有表头。")
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError("CSV 表头包含重复字段。")
            missing = set(self.REQUIRED_COLUMNS) - set(reader.fieldnames)
            if missing:
                raise ValueError("CSV 缺少必需字段：{}".format(sorted(missing)))
            for row_number, row in enumerate(reader, start=2):
                try:
                    bar = self._parse_row(row)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError("CSV 第 {} 行无效：{}".format(row_number, exc)) from exc
                bars.append(bar)

        if not bars:
            raise ValueError("CSV 行情不能为空。")
        bars.sort(key=lambda bar: bar.datetime)
        for previous, current in zip(bars, bars[1:]):
            if previous.datetime == current.datetime:
                raise ValueError("CSV 存在重复日期：{}".format(current.datetime.isoformat()))
        return iter(bars)

    def _parse_row(self, row: dict[str, Optional[str]]) -> Bar:
        """把一行原始字段转换为有 OHLCV 不变量的 Bar。"""
        raw_date = row.get("date")
        if raw_date is None or not raw_date.strip():
            raise ValueError("date 不能为空。")
        timestamp = datetime.fromisoformat(raw_date.strip())
        values: dict[str, float] = {}
        for name in ("open", "high", "low", "close", "volume"):
            raw_value = row.get(name)
            if raw_value is None or not raw_value.strip():
                raise ValueError("{} 不能为空。".format(name))
            value = float(raw_value)
            if not math.isfinite(value):
                raise ValueError("{} 必须是有限值。".format(name))
            values[name] = value
        return Bar(symbol=self.symbol, datetime=timestamp, **values)
