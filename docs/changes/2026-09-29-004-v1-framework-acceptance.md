# V1 基础量化框架验收与人工核算

## 基本信息

- 日期：2026-09-29
- 类型：Docs / Test
- 业务基线：`30f6a80`，包版本 `0.1.0`
- 影响范围：验收报告、正式集成测试；无业务代码与接口变化。

## 变更背景

用户要求验收整个框架是否能够作为基础个人量化研究/回测工具使用，并要求沿真实调用链验证成本、账户和止损，实际执行全部测试，至少一笔完整交易与人工计算一致。

## 变更内容

- 新增十一部分验收报告、功能状态矩阵及 A—L 条件证据，结论为当前单标的多头日线范围通过，未发现已复现的基础使用阻塞问题。
- 新增十根人工 CSV 的真实 MA/ATR 风险定仓交易测试，覆盖正常退出、盘中止损、跳空止损、买入当日止损。
- 补充非平坦绩效手算、信号前缀一致性、账户拒绝原子性、连续买入不加仓及待卖信号与止损优先级测试；共新增 10 项 pytest 用例。
- 记录公开分项盈亏不足、止损后等待新目标变化、未验证工具/环境等非阻塞边界。

## 涉及文件

- [验收报告](../v1_framework_acceptance_report.md)
- [正式验收测试](../../tests/integration/test_v1_acceptance.py)
- 本记录 `docs/changes/2026-09-29-004-v1-framework-acceptance.md`

## 设计决策

- 保留现有架构和业务规则，仅增加可复跑的验收证据，不用新增功能使框架“通过”。
- 用真实 MACrossStrategy 和 ATR 产生保护距离，不用预先写死买卖信号代替主要完整交易验收；订单优先级/连续 BUY 专项使用小型测试策略隔离触发条件。
- 手算断言保留独立常量，公共 Portfolio 接口重放成交；不跨层读取内部 `_position`。
- “V1”是用户本次基础验收标准，不更改版本号，不宣称实现长期路线中的 Paper Trading。
- README、architecture、TODO 已能描述当前链路；无功能/API 变化，不额外修改它们或版本 CHANGELOG。

## 测试与验证

- 基线 `python -m pytest -ra`：46 passed，0 failed/skipped/warning。
- 新用例首轮：6 passed、1 failed，原因是人工行情均线相等而提早卖出。将人工第六日 Close 从 12 调整为 13 以形成预定第七日下穿，并重新手算峰值；未改既有测试和业务规则。详情见验收报告。
- 最终 `python -m pytest -ra`：56 passed，0 failed/skipped/warning，0.75s。
- `$env:MPLBACKEND='Agg'; python -m examples.ma_cross_backtest`：成功，31 笔成交、期末权益 146173.52；1 条非 GUI 后端无法显示窗口的 UserWarning。
- 通过 `run_example('data/stock_real.csv')` 另核对：507 个快照、31 笔成交，期末权益 146173.52279237。
- `python -m ruff check .`、`python -m mypy quant`：无法运行，对应模块未安装；不声称通过。
- `git diff --check`：通过；读取 Git 状态及新增文件复核，业务文件无差异。
- Python AST 解析：`quant/` 全部源文件和新增测试无语法错误；新增测试可按 Python 3.8 语法解析，但没有实际执行 Python 3.8。
- 报告/记录相对链接及新增文件空白检查：通过。

## 潜在影响

运行行为、账户规则、Strategy/Broker/Portfolio/Engine/Analytics 接口和数据兼容性均无改变。新增测试只生成 pytest 临时目录内的 CSV，不覆盖仓库行情。

## 后续事项

按报告的非阻塞项决定是否补充只读分项 PnL、明确重入规则或增强失败路径测试；在安装开发依赖的隔离环境补跑 ruff/mypy 与最低 Python 版本。无本次验收要求的未完成业务开发。
