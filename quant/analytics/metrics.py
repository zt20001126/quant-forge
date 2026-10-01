"""基于初始资金和日终权益计算基础绩效指标。"""

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

from quant.core.validation import (
    validate_finite,
    validate_non_negative_finite,
    validate_positive_finite,
)
from quant.engine.models import BacktestResult

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class PerformanceMetrics:
    """收益与回撤均为比例；年化和 Sharpe 使用 252 个交易日口径。"""

    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float


def calculate_performance(
    result: BacktestResult,
    annual_risk_free_rate: float = 0.0,
) -> PerformanceMetrics:
    """仅消费回测结果计算指标，初始资金作为收益和回撤的起始基准。"""
    return calculate_equity_performance(
        result.initial_cash,
        [snapshot.portfolio_value for snapshot in result.equity_curve],
        annual_risk_free_rate,
    )


def calculate_equity_performance(
    initial_cash: float,
    equity_values: Sequence[float],
    annual_risk_free_rate: float = 0.0,
) -> PerformanceMetrics:
    """共用日终权益公式；首个收益周期从初始资金到首日权益，不能重复插入初值。"""
    validate_finite(annual_risk_free_rate, "annual_risk_free_rate")
    if annual_risk_free_rate <= -1:
        raise ValueError("无风险年利率必须是大于 -100% 的有限值。")
    if not equity_values:
        raise ValueError("回测结果缺少 Equity Snapshot。")

    validate_positive_finite(initial_cash, "initial_cash")
    values = [initial_cash] + list(equity_values)
    for value in values:
        validate_non_negative_finite(value, "portfolio_value")

    total_return = values[-1] / initial_cash - 1
    validate_finite(total_return, "total_return")
    periods = len(equity_values)
    if values[-1] == 0:
        annualized_return = -1.0
    else:
        # 用观察到的日数年化；该值是历史区间 CAGR，不代表未来收益预测。
        try:
            annualized_return = (
                (values[-1] / initial_cash) ** (TRADING_DAYS_PER_YEAR / periods) - 1
            )
        except OverflowError as exc:
            raise ValueError("年化收益超出可表示的数值范围。") from exc
        if not math.isfinite(annualized_return):
            raise ValueError("年化收益超出可表示的数值范围。")

    peak = values[0]
    max_drawdown = 0.0
    for value in values[1:]:
        peak = max(peak, value)
        if peak > 0:
            # 回撤以负数表示相对历史峰值的跌幅，初始资金也参与峰值比较。
            max_drawdown = min(max_drawdown, value / peak - 1)

    daily_returns = [
        current / previous - 1
        for previous, current in zip(values, values[1:])
        if previous > 0
    ]
    for daily_return in daily_returns:
        validate_finite(daily_return, "daily_return")
    if len(daily_returns) < 2:
        sharpe = 0.0
    else:
        # 使用样本标准差与年化日收益，无风险利率按 252 个交易日折算。
        daily_risk_free = (1 + annual_risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
        excess_returns = [daily_return - daily_risk_free for daily_return in daily_returns]
        try:
            volatility = statistics.stdev(excess_returns)
            validate_finite(volatility, "volatility")
            sharpe = 0.0 if math.isclose(volatility, 0.0) else (
                statistics.mean(excess_returns) / volatility * math.sqrt(TRADING_DAYS_PER_YEAR)
            )
            validate_finite(sharpe, "sharpe_ratio")
        except (OverflowError, ValueError) as exc:
            raise ValueError("Sharpe 计算超出可表示的数值范围。") from exc

    return PerformanceMetrics(total_return, annualized_return, max_drawdown, sharpe)
