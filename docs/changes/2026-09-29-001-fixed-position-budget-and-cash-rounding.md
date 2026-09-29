# 修复整股仓位预算与卖出现金残差

## 基本信息

- 日期：2026-09-29
- 类型：Fix / Test
- 影响范围：Broker 整股可负担量、Engine 固定比例定量、Portfolio 卖出入账及对应测试。

## 变更背景

审查复现了两项边界错误。权益 100、仓位比例 29%、价格 1、零费用时，浮点比例预算变成 `28.999999999999996`，Engine 因而只成交 28 股。另一个允许在 `1e-8` 容差内入账的卖出，会把现金留在微小负值；之后 Analytics 会因资产为负拒绝结果。

## 变更内容

- Broker 新增按整股逐个候选并用十进制金额比较、含佣金的最大可负担数量方法；保留原连续数量方法。
- Engine 使用十进制计算权益比例预算，并通过 Broker 新方法限制可买整股数量。
- Portfolio 卖出后按与买入相同的现金容差将近零余额归零。
- 增加 Engine 29% 取整回归测试、整股小数金额与固定佣金边界测试，以及卖出后负现金回归测试。

## 涉及文件

- `quant/broker/broker.py`
- `quant/engine/backtest_engine.py`
- `quant/portfolio/portfolio.py`
- `tests/unit/test_position_sizer.py`
- `tests/unit/test_broker_portfolio.py`
- `CHANGELOG.md`

## 设计决策

- 整股可负担检查放在 Broker，因为它依据执行价和佣金模型判断成交预算；Engine 继续编排，Portfolio 继续唯一拥有账户状态。
- 保留 Broker 原连续数量 API，新增整股 API 供当前整股 Engine 使用。
- 现金残差复用现有 `1e-8` 容差和买入归零规则；超出容差的资金不足仍拒绝。

## 测试与验证

- 修复前定向回归：两项新测试均失败，分别实际得到 28 股和 `-4.999999969612645e-09` 现金。
- `python -m pytest -q`：30 passed。
- `conda run -n agent python -m ruff check quant/broker/broker.py quant/engine/backtest_engine.py quant/portfolio/portfolio.py tests/unit/test_position_sizer.py tests/unit/test_broker_portfolio.py`：通过。
- `conda run -n agent python -m mypy quant`：通过，检查 30 个源文件。
- 未执行示例全量回测；此次修改限于整股边界和卖出近零现金，不改默认仓位比例、价格、佣金或滑点模型。

## 潜在影响

Engine 新增调用 Broker 的整股可负担方法，不更改 BacktestEngine 构造器或交易领域数据结构。卖出现金在已有容差范围内的近零正负残差会统一成为零。

## 后续事项

无。
