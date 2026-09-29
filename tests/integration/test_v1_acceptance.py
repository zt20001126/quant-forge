"""以十根人工行情核对实际 MA/ATR、成交成本及账户闭环。"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Sequence

import pytest
from quant.analytics.metrics import calculate_performance
from quant.broker.broker import SimulatedBroker
from quant.broker.commission import PercentageCommission
from quant.broker.slippage import FixedSlippage
from quant.core import Bar, OrderIntent, Side
from quant.data.csv_feed import CSVDataFeed
from quant.engine.backtest_engine import BacktestEngine
from quant.engine.models import BacktestResult, EquitySnapshot
from quant.indicators import average_true_range, simple_moving_average
from quant.portfolio.portfolio import Portfolio
from quant.portfolio.position_sizer import FixedFractionPositionSizer, RiskBasedPositionSizer
from quant.strategy.ma_cross import MACrossStrategy


def write_manual_bars(path: Path, scenario: str) -> None:
    """生成可手算的十根行情；仅改变止损触发 Bar 的 Open/Low。"""
    closes = [10, 10, 10, 12, 12, 13, 11, 10, 10, 10]
    rows = []
    for index, close in enumerate(closes):
        opening, high, low = close, close + 1, close - 1
        if scenario == "intraday_stop" and index == 5:
            low = 9
        elif scenario == "gap_stop" and index == 5:
            opening, low = 8, 7
        elif scenario == "entry_bar_stop" and index == 4:
            low = 9
        day = datetime(2024, 1, 1) + timedelta(days=index)
        rows.append(f"{day.date()},{opening},{high},{low},{close},100\n")
    path.write_text("date,open,high,low,close,volume\n" + "".join(rows), encoding="utf-8")


@pytest.mark.parametrize(
    "scenario,sell_day,sell_price,sell_commission,final_cash",
    [
        ("strategy_exit", 8, 9.9, 3.267, 920.14),
        ("intraday_stop", 6, 9.0, 2.97, 890.737),
        ("gap_stop", 6, 7.9, 2.607, 854.8),
        ("entry_bar_stop", 5, 9.0, 2.97, 890.737),
    ],
)
def test_manual_round_trip(
    tmp_path: Path,
    scenario: str,
    sell_day: int,
    sell_price: float,
    sell_commission: float,
    final_cash: float,
) -> None:
    """独立手算常量核对数量、费用、现金、成本及最终盈亏。"""
    path = tmp_path / "manual.csv"
    write_manual_bars(path, scenario)
    bars = list(CSVDataFeed(path, "AAA"))
    assert simple_moving_average([bar.close for bar in bars], 2)[3] == 11
    assert simple_moving_average([bar.close for bar in bars], 3)[3] == pytest.approx(32 / 3)
    assert average_true_range(bars, 1)[3] == 3
    portfolio = Portfolio(1000, "AAA")
    result = BacktestEngine(
        CSVDataFeed(path, "AAA"),
        MACrossStrategy(2, 3, atr_period=1, atr_multiplier=1),
        SimulatedBroker(PercentageCommission(0.01), FixedSlippage(0.1)),
        portfolio,
        RiskBasedPositionSizer(0.1),
    ).run()
    assert len(result.trades) == 2
    buy, sell = result.trades
    assert (buy.side, sell.side) == (Side.BUY, Side.SELL)
    assert buy.signal_time == bars[3].datetime
    assert buy.execution_time == bars[4].datetime
    assert buy.quantity == sell.quantity == 33
    assert buy.price == pytest.approx(12.1)
    assert buy.commission == pytest.approx(3.993)
    assert sell.execution_time == bars[sell_day - 1].datetime
    assert sell.price == pytest.approx(sell_price)
    assert sell.commission == pytest.approx(sell_commission)
    assert all(trade.execution_time > trade.signal_time for trade in result.trades)
    assert all(item.status.value == "FILLED" for item in result.order_results)
    assert not result.pending_orders
    assert len(result.equity_curve) == 10
    assert portfolio.cash == pytest.approx(final_cash)
    assert portfolio.position_quantity == 0
    assert result.equity_curve[-1].portfolio_value == pytest.approx(final_cash)
    for snapshot in result.equity_curve:
        assert snapshot.cash >= 0
        assert snapshot.quantity is not None and snapshot.quantity >= 0
        assert snapshot.portfolio_value == pytest.approx(snapshot.cash + snapshot.market_value)
    # 仅通过公开入账/估值接口重放成交，不读取 Portfolio 私有持仓。
    replay = Portfolio(1000, "AAA")
    replay.apply_trade(buy)
    account = replay.mark_to_market(12)
    assert account.cash == pytest.approx(596.707)
    assert account.average_price == pytest.approx(12.221)
    assert account.market_value == 396
    assert account.portfolio_value == pytest.approx(992.707)
    assert account.market_value - account.average_price * account.quantity == pytest.approx(-7.293)
    replay.apply_trade(sell)
    assert replay.cash - 1000 == pytest.approx(final_cash - 1000)
    assert calculate_performance(result).total_return == pytest.approx(final_cash / 1000 - 1)
    # 正常退出场景第六日有浮盈峰值；止损场景的峰值仍为初始本金。
    peak = 1025.707 if scenario == "strategy_exit" else 1000
    assert calculate_performance(result).max_drawdown == pytest.approx(final_cash / peak - 1)


def test_nonflat_performance_matches_manual_formulas() -> None:
    """初始本金参与峰值；上涨后下跌的非零回撤可人工核对。"""
    snapshots = tuple(
        EquitySnapshot(datetime(2024, 1, 1) + timedelta(days=i), value, "AAA", 0, 10, 0, value)
        for i, value in enumerate([90, 120, 96])
    )
    result = BacktestResult(100, (), snapshots, (), ())
    metrics = calculate_performance(result)
    assert metrics.total_return == pytest.approx(-0.04)
    assert metrics.max_drawdown == pytest.approx(-0.2)
    assert metrics.annualized_return == pytest.approx(0.96**84 - 1)
    # 日收益为 -1/10, 1/3, -1/5；均值 1/90，样本方差 217/2700。
    assert metrics.sharpe_ratio == pytest.approx((1 / 90) / (217 / 2700)**0.5 * 252**0.5)


def test_future_suffix_does_not_change_existing_signals(tmp_path: Path) -> None:
    """截断历史与追加未来数据的信号前缀一致，策略不读取后缀。"""
    path = tmp_path / "manual.csv"
    write_manual_bars(path, "strategy_exit")
    bars = list(CSVDataFeed(path, "AAA"))

    def signals(sequence: list[Bar]) -> list[OrderIntent]:
        strategy = MACrossStrategy(2, 3, atr_period=1, atr_multiplier=1)
        return [
            intent
            for index, bar in enumerate(sequence)
            for intent in strategy.on_bar(bar, sequence[:index])
        ]

    assert signals(bars[:5]) == [
        intent for intent in signals(bars) if intent.signal_time <= bars[4].datetime
    ]


def test_duplicate_and_invalid_trades_leave_account_unchanged(tmp_path: Path) -> None:
    """重复入账、超额卖出与现金不足均应拒绝且保持原账户。"""
    from dataclasses import replace

    path = tmp_path / "manual.csv"
    write_manual_bars(path, "strategy_exit")
    result = BacktestEngine(
        CSVDataFeed(path, "AAA"), MACrossStrategy(2, 3),
        SimulatedBroker(PercentageCommission(0.01), FixedSlippage(0.1)),
        Portfolio(1000, "AAA"), FixedFractionPositionSizer(0.5),
    ).run()
    buy = result.trades[0]
    portfolio = Portfolio(1000, "AAA")
    portfolio.apply_trade(buy)
    before = portfolio.mark_to_market(12)
    for invalid in (
        buy,
        replace(buy, trade_id="too-large-buy", quantity=1000),
        replace(buy, trade_id="too-large-sell", side=Side.SELL, quantity=1000),
    ):
        with pytest.raises(ValueError):
            portfolio.apply_trade(invalid)
        assert portfolio.mark_to_market(12) == before


def test_repeated_buy_intents_do_not_add_to_existing_position(tmp_path: Path) -> None:
    """连续买入目标不会加仓或耗尽账户剩余现金。"""
    class RepeatedBuyStrategy:
        def on_bar(self, bar: Bar, history: Sequence[Bar]) -> list[OrderIntent]:
            return [OrderIntent(bar.symbol, 1, bar.datetime)]

    path = tmp_path / "manual.csv"
    write_manual_bars(path, "strategy_exit")
    result = BacktestEngine(
        CSVDataFeed(path, "AAA"), RepeatedBuyStrategy(),
        SimulatedBroker(PercentageCommission(0.01), FixedSlippage(0.1)),
        Portfolio(1000, "AAA"),
    ).run()
    assert len(result.trades) == 1
    assert result.trades[0].quantity == 98
    assert result.equity_curve[-1].cash == pytest.approx(0.302)
    assert result.equity_curve[-1].quantity == 98


@pytest.mark.parametrize("scenario,final_cash", [("intraday_stop", 1018.15), ("gap_stop", 854.8)])
def test_due_sell_and_stop_follow_documented_priority(
    tmp_path: Path, scenario: str, final_cash: float,
) -> None:
    """跳空止损先于待卖单；开盘主动卖出先于随后盘中止损。"""
    class EntryThenExitStrategy:
        def on_bar(self, bar: Bar, history: Sequence[Bar]) -> list[OrderIntent]:
            if len(history) == 3:
                return [OrderIntent(bar.symbol, 1, bar.datetime, 3)]
            if len(history) == 4:
                return [OrderIntent(bar.symbol, 0, bar.datetime)]
            return []

    path = tmp_path / "manual.csv"
    write_manual_bars(path, scenario)
    result = BacktestEngine(
        CSVDataFeed(path, "AAA"), EntryThenExitStrategy(),
        SimulatedBroker(PercentageCommission(0.01), FixedSlippage(0.1)),
        Portfolio(1000, "AAA"), RiskBasedPositionSizer(0.1),
    ).run()
    assert [trade.side for trade in result.trades] == [Side.BUY, Side.SELL]
    assert len(result.order_results) == 2
    assert result.equity_curve[-1].quantity == 0
    assert result.equity_curve[-1].cash == pytest.approx(final_cash)
