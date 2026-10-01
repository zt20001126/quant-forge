"""绘制价格、成交信号与组合权益。"""

from __future__ import annotations

from typing import Optional, Sequence

from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.figure import Figure

from quant.analytics.benchmark import BuyAndHoldBenchmarkResult, validate_benchmark_alignment
from quant.core.bar import Bar
from quant.core.enums import Side
from quant.engine.models import BacktestResult


def plot_backtest(
    bars: Sequence[Bar], result: BacktestResult, show: bool = True, title: Optional[str] = None,
    *, benchmark: Optional[BuyAndHoldBenchmarkResult] = None,
) -> Figure:
    """显示回测图：收盘价方向、真实成交点和每日组合权益。"""
    from matplotlib import pyplot as plt
    from matplotlib.font_manager import FontProperties, fontManager

    if not bars:
        raise ValueError("绘图行情不能为空。")
    if not result.equity_curve:
        raise ValueError("回测结果缺少权益曲线，无法绘图。")
    if benchmark is not None:
        validate_benchmark_alignment(result, benchmark)
        if len(bars) != len(result.equity_curve) or any(
            bar.datetime != snapshot.timestamp or bar.symbol != snapshot.symbol
            or bar.close != snapshot.close_price
            for bar, snapshot in zip(bars, result.equity_curve)
        ):
            raise ValueError("绘图行情必须与策略快照逐日一致。")

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
        ("收盘价", "买入成交", "卖出成交", "组合权益", "价格", "日期")
        if cjk_font
        else ("Close", "Buy", "Sell", "Portfolio value", "Price", "Date")
    )
    (
        close_label,
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
    if benchmark is not None:
        # 基准曲线由 Analytics 提供，展示层不自行生成或改变估值。
        equity_axis.plot(
            [point.timestamp for point in benchmark.equity_curve],
            [point.equity_value for point in benchmark.equity_curve],
            color="#e67e22", linestyle="--", label="Buy & Hold (no costs)",
        )
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
