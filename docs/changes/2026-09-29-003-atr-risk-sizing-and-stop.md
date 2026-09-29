# ATR 风险定仓与固定保护止损

## 基本信息

- 日期：2026-09-29
- 类型：Feature
- 影响范围：Strategy、Position Sizer、Order、Broker、Risk Policy、Backtest Engine、文档

## 变更背景

ATR 指标此前只能单独计算，不能参与信号意图、风险定仓或成交后的保护止损。此次将用户确认的最小闭环接入现有模块，同时保持 Engine 只编排、Broker 执行成交规则、Portfolio 独占账户状态。

## 变更内容

- MA Cross 可选配置 ATR 周期和倍数，给买入意图附加 ATR 止损距离；ATR 未就绪时延迟信号。
- 新增 `RiskBasedPositionSizer`，按权益风险预算除以止损距离计算整股数量，并受滑点报价、佣金与可用现金限制。
- 新增 ATR 固定止损策略状态；买入入账后以实际成交价锚定止损，跳空按 Open、日内触及按止损价作为 Broker 参考价，再应用滑点和佣金。
- 新增止损市价订单类型；Broker 返回 Trade 后仍由 Portfolio 入账。
- 更新架构、使用范围、V0.1 任务状态和变更日志。

## 涉及文件

- `quant/core/enums.py`
- `quant/core/order.py`
- `quant/strategy/ma_cross.py`
- `quant/portfolio/position_sizer.py`
- `quant/portfolio/__init__.py`
- `quant/risk/atr_stop.py`
- `quant/risk/__init__.py`
- `quant/broker/broker.py`
- `quant/engine/backtest_engine.py`
- `tests/unit/test_core.py`
- `tests/unit/test_position_sizer.py`
- `tests/unit/test_broker_portfolio.py`
- `tests/unit/test_data_indicators_strategy.py`
- `tests/integration/test_backtest.py`
- `README.md`
- `docs/architecture.md`
- `docs/V0.1_TODO.md`
- `CHANGELOG.md`

## 设计决策

- 止损距离作为买入 `OrderIntent` 的可选风险参数；Strategy 不读取账户或改持仓。
- 风险定仓使用 `floor(Equity × RiskFraction / StopDistance)`。实际买入仍受现金和含费可支付数量上限约束。
- 止损在买入真实成交并入账后激活，止损价为成交价减止损距离，不支持追踪。
- OHLC 日线无法还原盘中路径；若 Open 已跌穿止损则按 Open 参考价，若 Low 触及则按止损价参考，并继续应用卖出滑点/佣金。跳空与成本可能导致实际损失超过预算。
- 未增加通用 RiskManager，以真实使用中的最小止损规则模块承载状态和触发判断。

## 测试与验证

- `python -m pytest tests/unit/test_core.py tests/unit/test_position_sizer.py tests/unit/test_broker_portfolio.py tests/unit/test_data_indicators_strategy.py tests/integration/test_backtest.py -q`：34 passed。
- `python -m pytest -q`：46 passed。
- `conda run -n agent python -m ruff check .`：All checks passed。
- `conda run -n agent python -m mypy quant`：33 source files，no issues found。
- `$env:MPLBACKEND='Agg'; python -m examples.ma_cross_backtest`：退出码 0，31 笔交易；非 GUI 后端提示无法显示图表窗口，回测计算和摘要输出正常。
- `git diff --check`：通过。

## 潜在影响

- `PositionSizer` 协议增加 `allocation_budget` 与可选 `stop_distance` 参数；现有固定比例使用方式和 Engine 默认满仓语义保留。
- RiskBasedPositionSizer 需配合携带保护止损距离的买入意图；无止损距离会明确报错。
- 日线止损模型为近似模型，且名义风险预算不包含跳空损失；滑点和费用可能扩大亏损。

## 后续事项

- 无。本阶段不实现移动止损、分批止盈或多资产风险预算。
