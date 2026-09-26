"""行情数据源及适配器。"""

from quant.data.base import DataFeed
from quant.data.csv_feed import CSVDataFeed

__all__ = ["DataFeed", "CSVDataFeed"]
