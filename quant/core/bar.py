"""单标的单周期 OHLCV 行情对象。"""

from dataclasses import dataclass
from datetime import datetime

from quant.core.validation import (
    validate_datetime,
    validate_non_negative_finite,
    validate_positive_finite,
    validate_symbol,
)


@dataclass(frozen=True)
class Bar:
    symbol: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_datetime(self.datetime, "datetime")
        for field_name in ("open", "high", "low", "close"):
            validate_positive_finite(getattr(self, field_name), field_name)
        validate_non_negative_finite(self.volume, "volume")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high 必须不低于 open、close 和 low。")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low 必须不高于 open、close 和 high。")
