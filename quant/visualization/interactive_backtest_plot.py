"""Plotly 交互式回测结果图；仅消费行情和结果中的已有数据。"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from quant.core.bar import Bar
from quant.core.enums import Side
from quant.engine.models import BacktestResult


def plot_interactive_backtest(
    bars: Sequence[Bar],
    result: BacktestResult,
    indicators: Optional[Mapping[str, Sequence[Optional[float]]]] = None,
    stop_prices: Optional[Sequence[Optional[float]]] = None,
    title: str = "Backtest",
) -> go.Figure:
    """构建共享时间轴的价格、权益和回撤图。

    indicators 与 stop_prices 由调用方按 bars 顺序提供；长度必须与行情一致。
    当前 BacktestResult 不保存每日止损价，故不会自行推测该序列。
    """
    if not bars:
        raise ValueError("绘图行情不能为空。")
    if not result.equity_curve:
        raise ValueError("回测结果缺少权益曲线，无法绘图。")
    if len(result.equity_curve) != len(bars):
        raise ValueError("权益曲线长度必须与行情一致。")
    if any(
        snapshot.timestamp != bar.datetime
        for bar, snapshot in zip(bars, result.equity_curve)
    ):
        raise ValueError("权益快照时间必须与行情时间逐日对应。")
    if indicators and any(len(values) != len(bars) for values in indicators.values()):
        raise ValueError("指标序列长度必须与行情一致。")
    if stop_prices is not None and len(stop_prices) != len(bars):
        raise ValueError("止损序列长度必须与行情一致。")

    dates = [bar.datetime for bar in bars]
    equity_values = [snapshot.portfolio_value for snapshot in result.equity_curve]
    peaks: list[float] = []
    peak = result.initial_cash
    for value in equity_values:
        peak = max(peak, value)
        peaks.append(peak)
    drawdowns = [value / high - 1 for value, high in zip(equity_values, peaks)]

    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.58, 0.24, 0.18],
        subplot_titles=("Price", "Portfolio Equity", "Drawdown"),
    )
    ohlcv = [
        [bar.open, bar.high, bar.low, bar.close, bar.volume]
        for bar in bars
    ]
    figure.add_trace(
        go.Scatter(
            x=dates,
            y=[bar.close for bar in bars],
            mode="lines",
            name="Close",
            line={"color": "#34495e", "width": 1.6},
            customdata=ohlcv,
            hovertemplate=(
                "Date: %{x|%Y-%m-%d}<br>Open: %{customdata[0]:.4f}"
                "<br>High: %{customdata[1]:.4f}<br>Low: %{customdata[2]:.4f}"
                "<br>Close: %{customdata[3]:.4f}<br>Volume: %{customdata[4]:,.0f}"
                "<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )
    for name, values in (indicators or {}).items():
        figure.add_trace(
            go.Scatter(x=dates, y=list(values), mode="lines", name=name), row=1, col=1
        )
    if stop_prices is not None:
        figure.add_trace(
            go.Scatter(
                x=dates, y=list(stop_prices), mode="lines", name="Stop loss",
                line={"color": "#e67e22", "dash": "dash"},
            ),
            row=1,
            col=1,
        )

    for side, name, color, symbol in (
        (Side.BUY, "BUY", "#159447", "triangle-up"),
        (Side.SELL, "SELL", "#c0392b", "triangle-down"),
    ):
        trades = [trade for trade in result.trades if trade.side == side]
        if trades:
            customdata = [
                [trade.quantity, trade.commission, trade.signal_time.strftime("%Y-%m-%d")]
                for trade in trades
            ]
            figure.add_trace(
                go.Scatter(
                    x=[trade.execution_time for trade in trades],
                    y=[trade.price for trade in trades],
                    mode="markers",
                    name=name,
                    marker={"symbol": symbol, "size": 12, "color": color},
                    customdata=customdata,
                    hovertemplate=(
                        "Date: %{x|%Y-%m-%d}<br>" + name + " @ %{y:.4f}"
                        "<br>Quantity: %{customdata[0]:.4f}"
                        "<br>Commission: %{customdata[1]:.4f}"
                        "<br>Signal date: %{customdata[2]}"
                        "<br>Slippage: embedded in fill price; amount unavailable"
                        "<extra></extra>"
                    ),
                ),
                row=1,
                col=1,
            )

    figure.add_trace(
        go.Scatter(x=dates, y=equity_values, mode="lines", name="Portfolio Equity"),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=dates,
            y=drawdowns,
            mode="lines",
            name="Drawdown",
            fill="tozeroy",
            line={"color": "#c0392b"},
            hovertemplate="Date: %{x|%Y-%m-%d}<br>Drawdown: %{y:.2%}<extra></extra>",
        ),
        row=3,
        col=1,
    )
    figure.update_layout(
        title=title,
        hovermode="x unified",
        dragmode="pan",
        height=850,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        margin={"l": 60, "r": 30, "t": 100, "b": 60},
    )
    # rangeslider 放在最下方面板；Plotly 的共享 x 轴会同步缩放与平移。
    figure.update_xaxes(matches="x", showspikes=True, spikemode="across", spikesnap="cursor")
    figure.update_xaxes(rangeslider={"visible": True, "thickness": 0.08}, row=3, col=1)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Equity", row=2, col=1)
    figure.update_yaxes(title_text="Drawdown", tickformat=".0%", row=3, col=1)
    return figure
