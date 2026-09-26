# Quant Framework 架构

> 本文是 Quant Forge 开发期间维护的架构基线，依据 `docs/Personal_Quant_Framework_架构设计与长期演进指南.md` 并记录 V0.1 的实际实现。旧 Demo 独立位于相邻的 `quant-learning` 项目；本文只约束 Quant Forge。架构变化需同步更新本文并说明影响。

## 1. 当前代码与回测流程

Quant Forge 是独立的 `src/quant` 项目，包含项目配置 `pyproject.toml`、测试 `tests/`、入口示例 `examples/ma_cross_backtest.py` 及示例行情 `data/stock_real.csv`。旧 Demo 的模块和 `main.py` 不在本项目中；它独立保留在 `E:\Quant\quant-learning`，仅供人工行为对照。

当前完整流程：

```text
main.run_backtest
  → load_stock_data (CSV 读取、必需列/空值检查、日期排序)
  → calculate_ma (pandas rolling close)
  → MovingAverageStrategy.generate_signal (整段 DataFrame → 对齐的信号 Series)
  → BacktestEngine.run (逐行读取信号；同日收盘买卖；同日收盘估值)
  → Broker (持有 cash/position；满仓买入或全仓卖出；扣佣金；估值)
  → trades + equity_curve DataFrame
  → calculate_performance (收益、回撤、Sharpe)
  → plot_backtest + print_summary
```

Demo 可作行为参考，但其当日收盘信号按当日收盘成交的假设不应作为 V0.1 的正确性基准。新框架现有自动化单元及集成测试；旧结构和入口继续保留，供后续行为参考与迁移验证。

## 2. V0.1 目标分层

V0.1 采用指南建议的 `src/quant` 布局，按实际职责逐步建立文件；不要求先创建没有实现内容的空模块。

| 层/模块 | 负责 | 不负责 |
|---|---|---|
| `core` | 无第三方基础设施依赖的领域对象和值语义：Bar、Side/Order 类型、OrderIntent、Order、Trade、Position，以及有明确需要的枚举 | CSV 解析、pandas 适配、成交、账户记账、策略规则 |
| `data` | DataFeed 抽象与 CSV 日线适配；字段、值、日期顺序和重复记录策略校验；按时间产生 Bar | 信号生成、账户状态、成交与指标决策 |
| `indicators` | 计算明确输入行情序列的指标（V0.1 为简单移动平均） | 读取文件、交易决策、账户更新 |
| `strategy` | 消费当前/历史可用行情与指标状态，输出 `OrderIntent`；包含 MA Cross 实现 | 选择数据源、检查或更改现金/持仓、决定成交价、扣费 |
| `broker` | 将 Engine 提交的订单按执行规则转成 Trade；应用佣金与滑点模型；拒绝不可成交订单并返回明确结果 | 产生策略信号、持有 Portfolio 的账户状态、计算绩效 |
| `portfolio` | 维护现金、单标的 Position，应用 Trade，按可用行情估值并提供 Portfolio Value | 生成订单、决定成交价格、读取 CSV、计算策略指标 |
| `engine` | 推进单标的日线生命周期，协调 DataFeed、Strategy、Broker、Portfolio；收集交易与每日 Equity Snapshot 并构成 BacktestResult | 计算 MA/策略规则、撮合/佣金/滑点、直接改写模块私有状态、绩效分析 |
| `analytics` | 对不可变或只读回测结果计算总收益、年化收益、最大回撤和 Sharpe，并返回类型化指标对象 | 参与交易循环、修改成交或账户 |
| `examples` | 组装配置与对象、启动示例、输出结果 | 携带领域规则、绕过公共接口修改状态 |

V0.1 仅支持 CSV、单股票、日线、MA Cross、市价单、基础佣金/滑点、单持仓账户和基础绩效。RiskManager、PositionSizer、多资产、多策略、优化、事件总线、实盘等属于后续版本；V0.1 只保留必要的非法数量、资金不足和禁止负持仓校验，不预建未使用的扩展框架。

### 当前实现文件

```text
src/quant/core/       Bar、OrderIntent、Order、Trade、Position、枚举
src/quant/data/       DataFeed 协议与 CSVDataFeed
src/quant/indicators/ 简单移动平均
src/quant/strategy/   Strategy 协议与 MA Cross
src/quant/broker/     市价执行、佣金与滑点模型
src/quant/portfolio/  单标的账户、成交入账与估值
src/quant/engine/     BacktestEngine、BacktestResult、权益快照
src/quant/analytics/  基础绩效指标
examples/             新框架端到端示例
```

## 3. 依赖规则

允许的逻辑依赖方向：

```text
examples / composition root → engine + 具体适配器/实现
engine → core + DataFeed/Strategy/Broker/Portfolio 的公开接口
data、indicators、strategy、broker、portfolio → core 中稳定领域类型
analytics → BacktestResult / Equity Snapshot / Trade 等结果类型
```

具体规则：

- `core` 不依赖其他项目层，也不依赖 pandas、matplotlib 或 CSV 实现。
- 领域层之间只通过公开方法和领域对象协作；不得导入其他模块的私有属性或直接修改其内部容器。
- `strategy` 不导入 `data`、`broker`、`portfolio` 或 `engine` 的具体实现。
- `broker` 与 `portfolio` 分工：Broker 产生 Trade；Engine 将成交交给 Portfolio 入账。Broker 不成为第二个账户状态所有者。
- `engine` 可以依赖协作者接口，但不能反向成为领域模块依赖项。Analytics 依赖结果模型，不依赖正在运行的 Engine 实例。
- 禁止循环依赖。必要的接口放在依赖方向更稳定的位置（通常是 core 或所属模块公开边界），不以延迟导入掩盖错误的职责关系。
- pandas 允许留在 CSV/分析边界；传入核心生命周期的行情采用 Bar 等领域类型。只有实际需要的数据转换才建立适配，不为抽象而抽象。

## 4. 核心领域对象与接口

对象语义以设计指南为起点，按单标的日线 V0.1 控制字段：

- **Bar**：一个标的在一个时间点的 OHLCV；时间戳及价格/成交量有效性明确，进入领域流程后不再承载 CSV 行索引语义。
- **OrderIntent**：策略提出的目标仓位，不代表已批准或已成交；V0.1 的 `target_fraction` 仅为 0（空仓）或 1（满仓），实际股数只能在执行 Bar 到达后确定。
- **Order**：Engine 交给 Broker 执行的订单，含唯一标识、标的、方向、数量、订单类型及创建/可执行时间等 V0.1 所需字段。
- **Trade**：一次成交结果，至少表达订单关联、标的、方向、价格、数量、费用及执行时间。
- **Position**：Portfolio 中持仓数量和成本等状态；市场价值由明确估值价格计算，避免重复存储可推导值。
- **Portfolio**：现金与持仓状态的所有者；负责应用 Trade 和估值。
- **EquitySnapshot**：指定估值时点现金、持仓/市值及组合总资产的记录。
- **BacktestResult**：回测结束后供 Analytics、可视化和示例层消费的交易记录、Equity 序列及必要元数据。

公共边界以小而明确的接口为准：`DataFeed` 按时间顺序迭代 Bar；`Strategy` 接收当前 Bar（以及其明确提供、无未来数据的历史/指标上下文）并返回零个或多个 OrderIntent；`Broker` 执行 Order 并给出成交/拒绝结果；`Portfolio` 应用 Trade 并按价格估值；`BacktestEngine.run()` 产出 BacktestResult。佣金和滑点分别有可替换的最小模型接口。接口细节和字段以实现时的 ADR/本架构更新为准，不能在本文文字之外悄然扩展。

## 5. 信号时间、执行时间与生命周期

统一约定：`Signal Time` 是策略能够使用的信息截止时间；`Execution Time` 是 Broker 可执行订单的时点。不可使用尚未发生的数据。

V0.1 默认日线规则：在 T 日 Bar 完整可见后，Strategy 可用截至 T 日收盘的行情产生目标仓位意图；意图最早于下一根可用 Bar（通常 T+1）的 Open 执行。Engine 只排队意图，不在 T 日读取下一根价格或用未来价格确定订单数量。下一根 Bar 到达后，Engine 用当前 Open 和 Portfolio 当前现金向 Broker 获取滑点报价及最大可买数量，构造订单；Broker 对方向应用滑点并计算佣金，成功成交后 Engine 将 Trade 交由 Portfolio 入账；Portfolio 按该 Bar 的 Close 估值。若没有下一根 Bar，意图记录为未执行，不得回填到 T 日。

```text
逐根取得 Bar(T)
  → 执行此前 Bar 收盘后排队的意图（用 T 日 Open 定价和定量）
  → 成交则 Portfolio.apply_trade
  → 按明确估值时点更新账户快照
  → Strategy 消费完整的 Bar(T)，产生只在后续时点可执行的意图
  → Engine 保存待执行订单并进入下一根 Bar
结束 → 记录未执行订单状态与末日按收盘价估值的持仓
  → BacktestResult → Analytics / Visualization
```

每日收盘估值，成交发生在当日 Open；当日快照包含成交后账户按收盘价的市值。信号对应的意图和成交记录分别保留信号/执行时间。最后一根 Bar 生成的待执行意图没有下一次执行机会，结果将其标记为 `EXPIRED_NO_NEXT_BAR`；买入数量在没有执行价格时为空，末日持仓仍按收盘价计入 Equity。

## 6. 现有模块迁移映射与已知风险

| 现有实现 | 可复用/迁移的内容 | 需要调整的边界或风险 |
|---|---|---|
| `quant-learning/data/data_loader.py` | 路径检查、字段检查、日期解析排序的基础思路 | 数值列未显式校验；无 OHLC 关系、正价格、成交量及重复日期策略；Quant Forge CSVDataFeed 增加这些边界校验 |
| `quant-learning/indicators/moving_average.py` | rolling mean 的简单实现 | pandas DataFrame/Series 耦合；Quant Forge 改为轻量序列函数并定义暖机期 |
| `quant-learning/strategies/ma_strategy.py` | 短长窗口约束和均线关系信号概念 | 批量信号不表达订单意图；Quant Forge 使用逐 Bar 目标仓位意图 |
| `quant-learning/backtest/broker.py` | 买入含费不超现金、卖出扣费、正价格校验的业务经验 | 旧 Broker 同时拥有账户状态和成交职责；Quant Forge 拆分 Broker 与 Portfolio |
| `quant-learning/backtest/engine.py` | 逐日驱动的最小闭环 | 同日 Close 成交有前视偏差；Quant Forge 使用下一根 Open，并在执行时定量 |
| `quant-learning/metrics/performance.py` | 总收益、回撤和年化 Sharpe 初稿 | 年化收益缺失且收益基准边界含混；Quant Forge 明确初始资金基准和 252 日年化 |
| `quant-learning/visualization/plot.py` | 旧 Demo 图表交互与布局参考 | 尚未迁移到 Quant Forge；新结果模型目前由示例打印 |
| `quant-learning/main.py` | 可读的旧 composition root | 旧入口保持原样，仅用于行为对照；Quant Forge 有独立的新示例入口 |

以下风险清单针对旧 Demo；新框架已在 V0.1 生命周期中处理时间偏差、目标仓位与账户边界。清单用于说明迁移动机及旧结果限制：

1. **高：前视偏差**——当日收盘后才知道的信号以当日 Close 成交。V0.1 必须使用 Signal/Execution 时间分离并测试 T 收盘信号只能影响后续 Bar。
2. **高：策略与资金执行语义含混**——信号是状态变化还是目标仓位不明确；需由 OrderIntent/订单生命周期表达，避免重复买入、卖空或被忽略的信号。
3. **中：数据质量边界不足**——数值类型、无穷值、非法 OHLC、非正价格、重复日期及排序稳定性缺少明确策略。
4. **中：结果基准和绩效解释**——旧 Demo 的初始资金可能在第一条 Equity 记录前发生交易，且未计算年化收益；新框架用初始资金作为收益/回撤基准，并明示 252 日年化与无风险利率设定。
5. **中：末日持仓**——现 Demo 通过末日收盘估值体现持仓价值，但不产生平仓成交；V0.1 要将该行为与未执行末日信号清晰区分。

Quant Forge 已有 `pyproject.toml` 和单元/集成测试；仍未配置 formatter、静态类型检查或 CI。相邻旧 Demo 的 `main.py` 返回松散 dict，且保留原有 same-close 行为作为历史参考；Quant Forge 暂未实现可视化。当前目录不是 Git worktree，无法提供 Git 状态/差异审计。

## 7. 测试与行为基准

新实现有 Core 对象校验、Data 输入校验、Indicator 数值、Strategy 进出场、Broker 成交/费用/滑点、Portfolio 买卖与持仓不变量、Engine 生命周期与 T+1 执行、Analytics 基准边界的单元测试，以及 CSV 到结果的集成测试。测试覆盖空/非法行情、均线暖机、资金不足的可买数量计算、禁止负持仓、无下一根 Bar、末日持仓估值、费用/滑点及时序。

旧 Demo 保留作为实现行为参考，不把其同日 Close 成交结果作为正确性金标。迁移比较需分别标注：相同策略信号下可比的功能行为，以及由于 T+1 Open、佣金/滑点等新假设而预期不同的数值结果。V0.1 集成测试已使用小型确定性行情夹具验证订单时序和权益；真实数据仅用于人工差异比较。

V0.1 完成阶段已在同一 `data/stock_real.csv` 上进行一次运行对照：旧 Demo 为 31 笔交易、期末资产 139,307.19；新框架为 31 笔交易、期末资产 146,176.65（使用 0.0003 比例佣金和无滑点）。日期信号/次日 Open 执行改变了成交价和权益，因此数值差异是预期的迁移差异；这组真实行情结果只用于人工对照，确定性夹具的集成测试才是回归断言依据。

## 8. 后续演进原则

- 每个新能力先确认真实学习/实验需求、所属层和依赖，再引入最小接口；没有两个真实实现或明确替换需求时，不泛化出复杂插件体系。
- 先锁定时间语义、资金不变量和结果含义，再优化性能或增加策略数量。
- 一次只推进一个 TODO Phase，维持旧 Demo 可运行；接口或执行顺序变化时同步测试和本文。
- V0.2 仓位管理、V0.3 风控、V0.4 多资产、V0.5 Benchmark、V0.6 多策略、V0.7 优化、V0.8 Walk Forward、V0.9 事件驱动、V1.0 Paper Trading，按指南路线演进，不提前实现。
- 所有核心架构变化都记录决策动机、影响和迁移办法。完整范围以上位文档 `docs/Personal_Quant_Framework_架构设计与长期演进指南.md` 为依据。
