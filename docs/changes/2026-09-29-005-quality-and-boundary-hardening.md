# 代码质量与交易边界修复

- 日期：2026-09-29
- 版本：V0.1 / Unreleased
- 背景：全仓质量审查后，用户授权直接修复，并在本地 Conda `agent` 环境安装依赖、执行测试。
- 原则：保留现有模块边界和下一根 Bar Open 执行语义，不增加空 RiskManager、事件总线或其他预建架构。

## 正确性修复

1. 合法的零 ATR 暂缓入场，不再构造零止损距离，也不提前记录目标已切换。
2. 旧仓开盘止损后，同日重新买入的新仓仍检查当前 Bar 的 Low；旧仓止损被拒绝时，不重复提交同一止损。
3. 数量与金额容差分离：严格禁止超持仓卖出，保留正的小额现金和残余持仓，仅对金额计算的微小负值使用现金容差。

## 审查问题与落实

| 审查项 | 实际修改 |
| --- | --- |
| P0：零 ATR、止损重入、数量容差 | 对应上述三项；加入正常、边界及失败回归测试。 |
| P1：公共参数校验不一致 | 共用有限数校验；拒绝非法均线窗口、止损参数、成本模型参数、NaN / Inf 和布尔数值；无效止损激活保持原状态。 |
| P1：OrderResult 契约松散 | FILLED 必须包含匹配订单编号的 Trade；其他状态不得带 Trade；编号和原因校验。 |
| P1：Sizer 双份可变配置 | 使用一个 Decimal 状态，公开比例改为只读属性。 |
| P1：假值自定义模型被默认模型覆盖 | 默认模型仅在参数为 None 时创建。 |
| P1：报价及可负担数量验证不一致 | 统一价格、资金、佣金校验；零资金返回零数量；非法成交报价产生明确拒绝结果。 |
| P1：绩效溢出与非有限结果 | 明确校验结果，对年化和 Sharpe 数值异常给出 ValueError，不返回 Inf / NaN。 |
| P1：Engine 重复路径及拒绝原因丢失 | 提取共有止损提交路径，区分目标已达成与拒绝；校验策略意图标的和时间，实际成交价止损校验先于入账。 |
| P1：测试断言不足 | 增加独立手算的成交、费用、现金、均价、权益、ATR 和收益断言。 |
| P1：Python 3.8 注解兼容 | 测试使用延迟注解，并补全公共测试辅助接口类型。 |
| P1：缺少质量门禁 | 新增 Python 3.8 / 3.10 / 3.12 CI；mypy 覆盖 quant、examples、tests 并要求函数注解。 |
| P2：重复计算历史指标 | SMA 只计算需要的最近窗口，ATR 只在入场目标变化时计算；未预建增量指标框架。 |
| P2：命名与字段语义 | 区分持仓方向与资金分配比例；权益快照数量为 float，待执行订单状态使用 Literal。 |
| P2：Docstring / 注释 | 补充公共边界和核心业务规则的必要中文说明。 |
| P2：文档和图表语义 | 区分 Portfolio 支持部分卖出与 Engine 默认全仓退出；图表采用通用标题并支持自定义。 |
| P2：测试洁净度 | 调整误导性测试名和局部 import；图表测试显式关闭 figure。 |
| P2：日志与示例参数 | 库使用标准 logging，不配置全局 handler；示例参数集中为不可变 ExampleConfig，佣金默认值共享。 |

## 涉及文件

- 核心契约：`quant/core/validation.py`、`order.py`、`trade.py`、`position.py`。
- 交易与账户：`quant/broker/{broker,commission,slippage}.py`、`quant/portfolio/{portfolio,position_sizer}.py`、`quant/risk/atr_stop.py`。
- 策略与编排：`quant/strategy/ma_cross.py`、`quant/engine/{backtest_engine,models}.py`。
- 分析与使用：`quant/analytics/metrics.py`、`quant/visualization/backtest_plot.py`、`examples/ma_cross_backtest.py`。
- 新增回归：`tests/integration/test_engine_regressions.py`、`tests/unit/test_boundary_contracts.py`。
- 加强现有测试：`tests/integration/test_backtest.py`；`tests/unit/` 中 ATR、数据策略、Broker/Portfolio、Sizer、图表相关测试。此前验收测试仅整理 import，保留原有场景。
- 工程与文档：`pyproject.toml`、`.github/workflows/quality.yml`、`README.md`、`docs/architecture.md`、`docs/V0.1_TODO.md`、`CHANGELOG.md`。历史验收报告增加后续修复说明，不替换历史结果。

## 接口与迁移影响

- Sizer 比例不可直接赋值；改变配置时创建新的 Sizer。
- 非法报价参数、资金或成本模型数值现在明确拒绝；调用方应提供合法有限数值，并按接口处理 ValueError / REJECTED。
- OrderResult 构造遵守状态与 Trade 的一致性；自定义策略的每条意图必须使用当前 Bar 的标的和信号时间。
- 绩效输入或结果超出有限数范围时抛出有意义的 ValueError。
- 新增 ExampleConfig 和可选图表标题，原有合法默认调用保持兼容。
- Broker、Portfolio、Strategy、Engine 的状态所有权与职责未变化。

## 实际验证

环境：`E:/KaFaEnvironment/.conda/envs/agent/python.exe`，Python 3.10.20。

```powershell
& 'E:/KaFaEnvironment/.conda/envs/agent/python.exe' -m pip install --no-build-isolation -e '.[dev]' --disable-pip-version-check
& 'E:/KaFaEnvironment/.conda/envs/agent/python.exe' -m pip check
& 'E:/KaFaEnvironment/.conda/envs/agent/python.exe' -m pytest -ra
& 'E:/KaFaEnvironment/.conda/envs/agent/python.exe' -m ruff check .
& 'E:/KaFaEnvironment/.conda/envs/agent/python.exe' -m mypy
git -c core.safecrlf=false diff --check
$env:MPLBACKEND='Agg'
& 'E:/KaFaEnvironment/.conda/envs/agent/python.exe' -m examples.ma_cross_backtest
```

- 修复前基线：56 项通过。第一批缺陷回归验证出现 20 项失败、4 项通过，随后完成修复。
- 最终完整测试：106 项通过，0 失败、0 跳过；最后执行耗时 2.76 秒。
- Ruff：全部通过；mypy：48 个源文件无问题；Git Diff 空白检查通过。
- 修改涉及的 Markdown 本地链接全部有效；48 个 Python 文件通过 Python 3.8 语法解析；33 个 quant 模块的直接 import 图未发现循环。这些静态检查不替代其他 Python 版本的运行验证。
- agent 环境依赖安装成功，`pip check` 无依赖冲突。
- 默认示例：31 笔成交，期末权益 146173.52，与修复前合法默认场景一致。Agg 下有不能弹出窗口的预期提示，未据此宣称 GUI 人工验收。
- CI 配置已提交到工作区，尚未在 GitHub 执行；本地没有实际运行 Python 3.8 / 3.12 矩阵。mypy 跳过当前 pytest 内部库解析，仍检查项目测试源码。

## 剩余边界

- 日线 OHLC 无法还原盘中价格路径；同日止损按文档确定的 Open / Low 规则处理。
- 保留浮点账户与金额容差；未进行 Decimal 账户迁移。
- 历史传递仍有序列复制，Wilder ATR 入场计算仍扫描历史；本次只消除明显的无效重复计算，未声称完成大数据性能优化。
- 仍是单标的 V0.1 框架，未引入组合账户、完整 RiskManager 或实盘执行能力。
