"""行情 Feed 的公开协议。"""

from __future__ import annotations

from typing import Iterator, Protocol

from quant.core.bar import Bar


class DataFeed(Protocol):
    def __iter__(self) -> Iterator[Bar]:
        """按时间顺序产生有效行情 Bar。"""
        ...
