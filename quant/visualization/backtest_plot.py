"""绘制价格、成交信号与组合权益。"""

from __future__ import annotations

from typing import Optional, Sequence

from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.figure import Figure

from quant.core.bar import Bar
from quant.core.enums import Side
from quant.engine.models import BacktestResult


def plot_backtest(
    bars: Sequence[Bar], result: BacktestResult, show: bool = True, title: Optional[str] = None,
) -> Figure:
    """显示回测图：收盘价方向、真实成交点和每日组合权益。"""
    from matplotlib import pyplot as plt
    from matplotlib.font_manager import FontProperties, fontManager

    if not bars:
        raise ValueError("绘图行情不能为空。")
    if not result.equity_curve:
        raise ValueError("回测结果缺少权益曲线，无法绘图。")

    installed_fonts = {font.name for font in fontManager.ttflist}
    cjk_font = next(
        (
            name
            for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC")
            if name in installed_fonts
        ),
        None,
    )
    font_properties = FontProperties(family=cjk_font or "DejaVu Sans")
    labels = (
        ("收盘价", "上涨日", "下跌日", "买入成交", "卖出成交", "组合权益", "价格", "日期")
        if cjk_font
        else ("Close", "Up day", "Down day", "Buy", "Sell", "Portfolio value", "Price", "Date")
    )
    (
        close_label,
        up_label,
        down_label,
        buy_label,
        sell_label,
        equity_label,
        price_label,
        date_label,
    ) = labels
    chart_title = title or (
        "回测：价格与成交信号" if cjk_font else "Backtest: Price and Trades"
    )

    dates = [bar.datetime for bar in bars]
    close_prices = [bar.close for bar in bars]
    figure, (price_axis, equity_axis) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
    )

    price_axis.plot(dates, close_prices, color="#34495e", linewidth=1.4, label=close_label)
    rising_indices = [
        index for index in range(1, len(bars)) if bars[index].close >= bars[index - 1].close
    ]
    falling_indices = [
        index for index in range(1, len(bars)) if bars[index].close < bars[index - 1].close
    ]
    rising_dates = [dates[index] for index in rising_indices]
    rising_prices = [close_prices[index] for index in rising_indices]
    falling_dates = [dates[index] for index in falling_indices]
    falling_prices = [close_prices[index] for index in falling_indices]
    price_axis.scatter(rising_dates, rising_prices, color="#2e8b57", s=14, label=up_label)
    price_axis.scatter(falling_dates, falling_prices, color="#d9534f", s=14, label=down_label)

    for side, marker, color, label in (
        (Side.BUY, "^", "#00a65a", buy_label),
        (Side.SELL, "v", "#c0392b", sell_label),
    ):
        side_trades = [trade for trade in result.trades if trade.side == side]
        if side_trades:
            # 标记使用实际成交时间和价格，而不是信号日收盘价。
            price_axis.scatter(
                [trade.execution_time for trade in side_trades],
                [trade.price for trade in side_trades],
                marker=marker,
                color=color,
                edgecolors="white",
                linewidths=0.7,
                s=100,
                label=label,
                zorder=3,
            )

    equity_axis.plot(
        [snapshot.timestamp for snapshot in result.equity_curve],
        [snapshot.portfolio_value for snapshot in result.equity_curve],
        color="#2878b5",
        linewidth=1.5,
        label=equity_label,
    )
    equity_axis.set_ylabel(equity_label, fontproperties=font_properties)
    equity_axis.set_xlabel(date_label, fontproperties=font_properties)
    price_axis.set_ylabel(price_label, fontproperties=font_properties)
    price_axis.set_title(chart_title, fontproperties=font_properties)
    price_axis.legend(loc="best", prop=font_properties)
    equity_axis.legend(loc="best", prop=font_properties)
    for axis in (price_axis, equity_axis):
        axis.grid(True, alpha=0.25)
        axis.xaxis.set_major_locator(AutoDateLocator())
        axis.xaxis.set_major_formatter(ConciseDateFormatter(axis.xaxis.get_major_locator()))
    figure.tight_layout()

    if show:
        plt.show()
    return figure
