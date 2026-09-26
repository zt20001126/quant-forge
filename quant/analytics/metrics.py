"""基于初始资金和日终权益计算基础绩效指标。"""

import math
import statistics
from dataclasses import dataclass

from quant.engine.models import BacktestResult

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float


def calculate_performance(
    result: BacktestResult,
    annual_risk_free_rate: float = 0.0,
) -> PerformanceMetrics:
    """仅消费回测结果计算指标，初始资金作为收益和回撤的起始基准。"""
    if not math.isfinite(annual_risk_free_rate) or annual_risk_free_rate <= -1:
        raise ValueError("无风险年利率必须是大于 -100% 的有限值。")
    if not result.equity_curve:
        raise ValueError("回测结果缺少 Equity Snapshot。")

    values = [result.initial_cash] + [snapshot.portfolio_value for snapshot in result.equity_curve]
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("组合资产必须是有限非负数。")
    if result.initial_cash <= 0:
        raise ValueError("初始资金必须大于 0。")

    total_return = values[-1] / result.initial_cash - 1
    periods = max(len(result.equity_curve), 1)
    if values[-1] == 0:
        annualized_return = -1.0
    else:
        # 用观察到的日数年化；该值是历史区间 CAGR，不代表未来收益预测。
        annualized_return = (
            (values[-1] / result.initial_cash) ** (TRADING_DAYS_PER_YEAR / periods) - 1
        )

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
    if len(daily_returns) < 2:
        sharpe = 0.0
    else:
        # 使用样本标准差与年化日收益，风险免费率按 252 个交易日折算。
        daily_risk_free = (1 + annual_risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
        excess_returns = [daily_return - daily_risk_free for daily_return in daily_returns]
        volatility = statistics.stdev(excess_returns)
        sharpe = 0.0 if math.isclose(volatility, 0.0) else (
            statistics.mean(excess_returns) / volatility * math.sqrt(TRADING_DAYS_PER_YEAR)
        )

    return PerformanceMetrics(total_return, annualized_return, max_drawdown, sharpe)
