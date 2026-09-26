# 固定比例仓位管理

## 基本信息

- 日期：2026-09-26
- 类型：Feature
- 影响范围：Portfolio 仓位计算、Engine 订单定量、文档与测试

## 变更背景

Engine 原先只按账户可负担资金决定买入数量，策略意图不包含数量。为支持每次买入按账户权益配置资金比例，同时保持策略、成交和账户状态职责边界，新增固定比例仓位计算。

## 变更内容

- 新增 `PositionSizer` 协议和 `FixedFractionPositionSizer`，验证 `position_ratio` 在 `(0, 1]`，以 Decimal 运算按整股向下取整。
- Engine 在下一根 Bar Open 执行时按该价格估值账户权益，用滑点报价定量；仓位额度、现金和 Broker 含佣金 affordability 共同限制 BUY 数量。
- SELL 仍按 Portfolio 当前持仓全部卖出，不通过买入仓位计算。
- README、架构基线、V0.1 范围和 CHANGELOG 同步记录功能与限制。
- 新增仓位计算和交易流程测试。

## 涉及文件

- `quant/portfolio/position_sizer.py`
- `quant/portfolio/__init__.py`
- `quant/engine/backtest_engine.py`
- `tests/unit/test_position_sizer.py`
- `README.md`
- `docs/architecture.md`
- `docs/V0.1_TODO.md`
- `CHANGELOG.md`

## 设计决策

- 仓位计算放在 Portfolio 领域包，但不读取或修改账户状态；Engine 将只读权益与执行报价传入。
- 默认比例为 1.0，以保持既有 Engine 构造方式下的满仓行为；用户可注入其他比例。
- 数量只支持整股；佣金被计入最大分配金额，减少实际买入额越过比例额度的风险。

## 测试与验证

- `pytest -q`：26 passed。
- `python -m unittest discover -s tests -v`：26 tests passed。
- `python -m pytest`：当前默认 Python 环境未安装 pytest；改用 PATH 上可用的项目 pytest 命令完整执行成功。
- `ruff` / `mypy`：未执行，当前环境未安装对应命令。
- `git diff --check`：通过；仅有 Git 对 LF→CRLF 自动转换的工作区提示。

## 潜在影响

Engine 增加可选 `position_sizer` 构造参数，既有四参数构造仍有效。比例小于 1 时新买入规模会变化；未实现部分卖出、小数股、多资产分配或风险型定仓。

## 后续事项

可在下一阶段讨论明确整手/交易单位（例如 A 股 100 股一手）及部分卖出接口；本次维持通用整股语义，不实现这些规则。
