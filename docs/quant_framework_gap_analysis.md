# QuantForge 基础能力与缺口审查报告

审查日期：2026-09-29。代码基线：`5d402e95ecab07025e19ed4d0ad7ff52023efadc`，包版本 V0.1.0。

本次完整检查当前实现，只新增本报告，没有修改代码、测试、配置或既有文档。审查开始时工作区干净。结论来自源码调用链、现有测试以及不落盘的手算/复现脚本；历史变更记录中的通过结果没有代替本次验证。

## 1. 核心结论与审查范围

当前已经具有完整的 **单股票、多头、日线 MA 回测闭环**：数据校验 → SMA → 目标仓位意图 → 固定比例整股定量 → 下一根 Open 成交 → 佣金/滑点 → 现金持仓更新 → 收盘权益 → 四项基础绩效。

**手续费和滑点均已真实实现并影响最终收益，并非只有配置。TR、ATR、基于风险的定仓和所有止损均未实现。** 因此它目前可以回测不带止损的 MA 策略，尚不能称为带单笔风险控制的完整框架。MA 死叉卖出不等于止损。

发现两项已复现的边界缺陷：固定比例预算的浮点误差可能少买一股；卖出后的微小负现金未归零，会被 Analytics 拒绝。现有 26 项测试通过，但未覆盖这两个问题及多项重要失败路径。

阅读范围包括：

- [长期架构指南](Personal_Quant_Framework_架构设计与长期演进指南.md)，随后阅读 [当前架构](architecture.md)、[V0.1 TODO](V0.1_TODO.md)。指南中的目标目录、RiskManager 和未来流程不能当作已实现事实。
- [README](../README.md)、[AGENTS](../AGENTS.md)、[项目配置](../pyproject.toml)、`.gitignore`、`.vscode/settings.json`、[CHANGELOG](../CHANGELOG.md)、现有 Change Records。
- `quant/` 全部 Python 源文件及包导出，`examples/ma_cross_backtest.py`，全部单元与集成测试，`data/stock_real.csv` 表头和通过 DataFeed 的完整加载。
- 不审查相邻旧 Demo 的业务代码；不导入 `quant-learning`，不以其同日 Close 成交作为正确性基准。

使用 code-review 技能的规范/需求双轴复核方法；本任务审查整个现状，以用户能力清单和当前架构为依据，不按提交差异审查，也不建立外部 issue tracker。

## 2. 当前架构概览

实际 Python 包在根目录 `quant/`，没有 `src/quant/`、`risk/`、`config/` 或独立 Account 包。

| 位置 | 实际职责与重要对象 |
|---|---|
| `quant/core/` | Bar、Side、OrderIntent、Order、OrderResult、Trade、Position；领域校验 |
| `quant/data/` | DataFeed Protocol；CSVDataFeed 加载、数值转换、校验、排序 |
| `quant/indicators/` | 只有 `simple_moving_average`，没有 TR/ATR |
| `quant/strategy/` | Strategy Protocol、MACrossStrategy；输出 0/1 目标意图 |
| `quant/portfolio/` | Portfolio 独占现金/持仓；AccountSnapshot；PositionSizer 和固定比例实现 |
| `quant/broker/` | SimulatedBroker、佣金模型、滑点模型；不保存账户 |
| `quant/engine/` | BacktestEngine、BacktestResult、EquitySnapshot、PendingOrder |
| `quant/analytics/` | 总收益、年化收益、最大回撤、Sharpe |
| `quant/visualization/` | 静态价格、真实成交点、权益曲线展示 |
| `examples/` | 组装协作者和输出；参数目前主要在这里指定 |
| `tests/unit/`、`tests/integration/` | 26 项测试；其中一个 CSV 到绩效的集成测试 |

依赖方向：Data/Indicator/Strategy/Broker/Portfolio → Core；Strategy → Indicator；Engine → 各协作者；Analytics/Visualization → 只读回测结果。未发现业务模块循环依赖、Strategy 直接操作账户或跨层写入内部持仓的情况。Broker 与 Portfolio 不互调，由 Engine 转交 Trade。

Engine 目前显式依赖唯一的 SimulatedBroker，这符合当前规模，无需为了第二种尚不存在的 Broker 新建抽象。数据和策略已有 Protocol，不需要强行改成抽象基类。

## 3. 当前回测完整执行流程

```text
examples.run_example：CSV 路径、标的、初始资金、MA 窗口、佣金/滑点组装
  ↓
CSVDataFeed：读取全部 CSV → 校验 OHLCV → 按 datetime 排序 → 拒绝重复时间
  ↓
Engine：读取全部 Bar，复核非空、单标的、严格递增、账户标的一致
  ↓ 每根 Bar T
执行上一根 Bar 形成的待执行意图
  ├─ BUY：已有仓位则忽略；空仓才定量
  │    T.Open 估值权益 → Broker.quote 得到含滑点价
  │    → PositionSizer 按权益比例向下取整
  │    → min(比例预算, 可用现金) + Broker 含佣金可负担数量 → Order
  └─ SELL：按已有数量全部卖出；空仓则忽略
  ↓
Broker.execute：T.Open → 方向滑点 → 实际成交价 → 佣金 → Trade / 拒绝结果
  ↓
Portfolio.apply_trade：校验 → 买入扣款/加仓 或 卖出回款/减仓 → 记录成交 ID
  ↓
Portfolio.mark_to_market(T.Close) → EquitySnapshot
  ↓
Strategy.on_bar(T, 仅 T 之前的 history)
  → 在 Strategy 内加入 T，计算截至 T 的 SMA
  → 空仓/持仓目标变化时发 OrderIntent；没有变化返回 []
  ↓
留到下一根可用 Bar Open 执行；末根新意图记 EXPIRED_NO_NEXT_BAR
  ↓
BacktestResult → calculate_performance → 图表/终端摘要
```

关键依据：[Engine](../quant/engine/backtest_engine.py) 的 `run`、`_create_order`；[策略](../quant/strategy/ma_cross.py) 的 `on_bar`；[Broker](../quant/broker/broker.py) 的 `execute`；[Portfolio](../quant/portfolio/portfolio.py) 的 `apply_trade`。

与用户期望流程相比，缺失的是 **风险金额/止损距离定量、止损规则和逐 Bar 止损执行**。普通成交流程已经贯通至回测绩效；并不是只实现到指标或下单。

### 时间与成交语义

- T.Close 生成信号，下一根可用 Bar.Open 执行；不是必然下一个自然日。Signal Time 与 Execution Time 分开记录，Order/Trade 验证执行晚于信号。
- Engine 虽一次加载全部数据，但只传当前 Bar 和历史前缀给内置 Strategy。预加载本身不等于前视；未发现内置策略或 SMA 使用未来 Bar。
- 定量用执行时 Open 与滑点报价，没有用当前 Close/High/Low 倒推开盘订单数量。Broker 成交不使用当根 Close。
- 最后一根信号不回填成交；最后持仓按 Close 估值，不强制平仓。因此最终权益包含浮盈亏，但不包含尚未发生的退出手续费/滑点。
- 策略使用均线状态而不是严格跨越：首次暖机完成且短均线较高即买入；两线相等时目标为 0。`target_fraction=1` 表示启用配置仓位，若配置比例 20%，实际并非 100% 仓位；持仓后也不会每日再平衡或加仓。

## 4. 能力矩阵

状态：✅ 已完整实现；⚠️ 部分实现；❌ 未实现；⏳ 当前阶段暂时不需要。完整是相对于单标的日线研究的明确能力，不表示覆盖所有真实市场规则。测试充分性单独列行，不能把“有实现”和“测试完备”混为一谈。

“是否当前必须”的“风控闭环”指下一套带 ATR/单笔风险控制的策略验收前；这属于后续版本扩展，不追溯要求已发布 V0.1 必须具有 RiskManager。

| 功能 | 状态 | 代码位置 | 当前实现 | 存在问题/边界 | 是否当前必须 |
|---|---|---|---|---|---|
| OHLCV | ✅ | `quant/core/bar.py`、`quant/data/csv_feed.py` | 完整五字段、正价格、非负量、OHLC 关系校验 | 不验证行情来源真实性 | 是 |
| 时间索引 | ✅ | `core/bar.py`、`data/csv_feed.py` | datetime 字段、ISO 解析 | 非 pandas 索引；未统一时区/交易日历 | 是 |
| CSV 数据加载 | ✅ | `data/base.py`、`data/csv_feed.py` | 可迭代 Feed、UTF-8 BOM 支持、必需列检查 | 只有 CSV 适配 | 是 |
| 数据清洗 | ⚠️ | `data/csv_feed.py` | 数值转换、日期去空白、排序、坏数据拒绝 | 无自动修复、填补、复权和来源元数据 | 基础校验是；自动修复否 |
| 缺失值处理 | ✅ | `data/csv_feed.py` | 空字段、NaN/Inf 拒绝；不偷偷填未来数据 | 不检测缺失整个交易日 | 是，拒绝策略已满足 |
| 时间顺序 | ✅ | `data/csv_feed.py`、`engine/backtest_engine.py` | 排序、重复时间拒绝、Engine 再检查 | 没有自然日补齐 | 是 |
| 单股票 | ✅ | `engine/backtest_engine.py`、`portfolio/portfolio.py` | 固定单标的、与账户一致 | 切换标的须新建协作者 | 是 |
| 多股票 | ⏳ | Engine 明确拒绝多标的 | 没有多持仓/时间对齐 | 当前不需要 | 否，P2 |
| 历史可见性/避免同 Close 前视 | ✅ | `engine/backtest_engine.py`、`strategy/ma_cross.py` | 截断历史、下一根 Open 执行 | 自定义策略仍须遵守协议 | 是 |
| MA / SMA | ✅ | `indicators/moving_average.py` | 滚动 SMA、可配窗口、暖机 None | 无统一指标注册器，当前无需 | 是 |
| MA5 | ✅ | `strategy/ma_cross.py` | 默认短窗 5，调用 SMA | 测试主要使用短窗 2 | 是 |
| MA20 | ✅ | `strategy/ma_cross.py` | 默认长窗 20，调用 SMA | 测试主要使用长窗 3 | 是 |
| TR | ❌ | 无 | 无 TR 计算 | ATR 的前置缺口 | 风控闭环，P0 |
| ATR/周期/调用接口 | ❌ | 无 | 无公式、周期、暖机、导出或调用 | 不能服务定仓与止损 | 风控闭环，P0 |
| 策略接口 | ✅ | `strategy/base.py` | Strategy Protocol、Bar/history → intents | 不需要额外 ABC | 是 |
| BUY / SELL / HOLD | ✅ | `core/order.py`、`strategy/ma_cross.py` | 1 买入意图、0 清仓意图、[] HOLD | 没有独立 HOLD 枚举，语义已具备 | 是 |
| 严格 MA5/20 金叉死叉 | ⚠️ | `strategy/ma_cross.py` | 均线高低状态变化策略 | 初始高位也买、相等也退出；不完全等于严格穿越 | 明确口径是；改规则须选择 |
| 策略参数可配置 | ✅ | `strategy/ma_cross.py` | 构造器配置短/长窗口 | 非整数在首次指标调用时才被拒绝 | 是 |
| Cash | ✅ | `portfolio/portfolio.py` | 公开只读 cash、买卖更新 | 容差缺陷见资金不变量行 | 是 |
| Position | ✅ | `core/position.py`、`portfolio/portfolio.py` | 单标的多头数量、均价 | 不支持多资产/空头 | 是 |
| Portfolio Value | ✅ | `portfolio/portfolio.py` | cash + quantity × mark_price | 无清算价值字段 | 是 |
| 买入现金变化 | ✅ | `portfolio/portfolio.py` | 扣成交金额 + 佣金 | 校验后更新 | 是 |
| 卖出现金变化 | ✅ | `portfolio/portfolio.py` | 加成交金额 - 佣金 | 极小负余额边界另列 | 是 |
| 持仓成本 | ✅ | `portfolio/portfolio.py` | 加权含买入佣金均价，清仓归零 | 不是裸成交均价，止损 Entry Price 要另定义 | 是 |
| 当前市值 | ✅ | `core/position.py`、`portfolio/portfolio.py` | quantity × 当前估值价 | 使用收盘/开盘的时点不同 | 是 |
| 已实现盈亏公开能力 | ⚠️ | `core/position.py`、`portfolio/portfolio.py` | 内部累加净已实现盈亏 | 不在公开快照/回测结果输出 | P1 |
| 未实现盈亏公开能力 | ❌ | 无字段/方法 | 可从公开均价/数量/mark_price 手算 | 没有正式接口或结果输出 | P1 |
| 固定股数仓位 | ❌ | 无 | 固定比例不等于固定股数 | 现有协议绑定 position_ratio | 非阻塞，P1 可选 |
| 固定百分比仓位端到端 | ⚠️ | `portfolio/position_sizer.py`、Engine | Decimal 定量、含费预算、可配置 | Engine 浮点预算导致 29 股变 28 股 | 是，P0 修复 |
| 基于风险的仓位/单笔风险比例 | ❌ | 无 | 无允许亏损金额 ÷ 止损距离 | 当前比例是资金分配比例，不是亏损风险比例 | 风控闭环，P0 |
| 买入现金上限 | ✅ | Engine、Broker、Portfolio | 比例/现金双预算，含费可负担量，最终入账校验 | 自定义模型须符合合同 | 是 |
| 整数股数量 | ✅ | `portfolio/position_sizer.py`、Engine | 非负整股、预算不足一股拒绝 | Domain/Broker/直接 Portfolio 接口仍允许小数股 | 是；整手规则另议 |
| 固定百分比止损 | ❌ | 无 | 无 stop price/触发/卖出 | 死叉不是止损 | 非阻塞，P1 替代规则 |
| 技术位置止损 | ⏳ | 无 | 无支撑位等规则 | 不阻塞选择 ATR 止损 | 否，P2 |
| ATR Stop/multiplier/逐 Bar 执行 | ❌ | 无 | 无止损距离、状态、判断、平仓 | 整条保护性退出链路缺失 | 风控闭环，P0 |
| Commission | ✅ | `broker/commission.py`、Broker、Portfolio | 比例/每笔固定佣金，买卖均扣、影响权益 | 没有市场特定最低佣金/税费 | 是，已有 |
| Slippage | ✅ | `broker/slippage.py`、Broker、Portfolio | 无/固定/百分比滑点，双方向生效 | 默认示例为零滑点，不代表没有模型 | 是，已有 |
| 初始资金 | ✅ | Portfolio、`examples/ma_cross_backtest.py` | 参数化 initial_cash，示例 100000 | 示例函数不直接暴露资金参数 | 是 |
| 每 Bar 生命周期 | ✅ | `engine/backtest_engine.py` | 先成交，再收盘估值，再生成下根意图 | 无止损阶段 | 是 |
| Order/Trade/拒绝/末根过期记录 | ✅ | `core/order.py`、Engine、`engine/models.py` | 成交/拒绝、时间关联、末根 pending | 末根状态为字符串；对象关联约束不全 | 是 |
| Equity Curve/最终资产 | ✅ | Engine、`engine/models.py` | 每 Bar 日终快照、最后权益 | 不自动清仓 | 是 |
| Total Return | ✅ | `analytics/metrics.py` | final / initial - 1 | 含未平仓市值、已发生费用 | 是 |
| Annualized Return | ✅ | `analytics/metrics.py` | 按 Bar 数和 252 日复合年化 | 输入非日线/漏交易日时口径不适用 | 是，仅日线假设 |
| Maximum Drawdown | ✅ | `analytics/metrics.py` | 含初始资金峰值、负数回撤 | 日终回撤，不是盘中回撤 | 是 |
| Sharpe Ratio | ✅ | `analytics/metrics.py` | 日超额收益、样本标准差、252 年化 | 短/零波动返回 0；非日线不适用 | 已有，继续保留 |
| Win Rate | ❌ | 无 | 无已平仓交易配对统计 | 不能用成交笔数当交易胜率 | 后续实现，P1 |
| Profit / Loss 报告 | ⚠️ | 权益/成本/内部 realized_pnl | 组合净盈亏可算、内部已实现计算 | 无公开盈亏拆分/每笔净盈亏报告 | 后续实现，P1 |
| 示例参数入口/运行配置 | ⚠️ | `examples/ma_cross_backtest.py`、构造器 | 库层可注入参数和模型 | run_example 仅 path/symbol，其他写在函数中 | P1，无需配置框架 |
| 资金/持仓基础不变量 | ⚠️ | `portfolio/portfolio.py` | 资金不足、超卖、重复成交校验 | 卖出容差允许负现金残留 | 是，P0 修复 |
| 基础能力测试完整性 | ⚠️ | `tests/` | 26 测试通过，覆盖主要正常流程 | 缺非零 MDD、卖出成本、重复入账等 | 是，P0 补强 |
| 特定市场规则 | ⏳ | 无 | 不含整手/T+1/涨跌停/停牌等 | 通用研究模拟不能宣称真实市场撮合 | 特定市场验收前需重新评估 |
| 复权/公司行为/退市样本 | ⏳ | 无 | 消费输入价格，无公司行为逻辑 | 数据口径须先核实，真实研究可能升级为 P0 | 合成教学非必需 |
| 高级交易/基础设施 | ⏳ | 无 | 无多策略、优化、实盘等 | 详见 P2 | 否 |

统计口径仅计算本矩阵各行一次；MA5/MA20 与通用 SMA 分列满足检查清单，所以这是能力检查项数，不是独立模块或功能开发数量。状态统计见第 14 节。

## 5. 已实现、部分实现、未实现及暂不需要的能力

### 已实现能力

数据到绩效的单标的闭环、SMA 及默认 5/20 窗口、策略协议和三态语义、市价单、整股定量、账户入账/估值、交易成本、订单结果/末根过期、四项绩效、静态可视化均有实际代码。收费和滑点不是空壳；账户查询也不是 Broker 内复制一份账户。

缺失值采取严格拒绝而非自动填补，是一种已实现且合理的处理策略。不要为了“数据清洗”数量而加前向/后向填充；后向填充尤其可能引入未来信息。

### 部分实现能力

数据清洗只有规范化/校验；严格金叉死叉语义不完整；固定比例端到端存在取整缺陷；已实现盈亏有内部累计但缺公开输出；综合盈亏报告、示例配置、资金不变量和测试覆盖不完整。没有发现“只定义 commission_rate 而从未扣款”这一类占位问题。

### 未实现能力

TR、ATR、风险定仓、ATR 止损、固定百分比止损、固定股数仓位、未实现盈亏输出、Win Rate。ATR/Stop/风险定仓连接口或配置都没有，不能归为“部分实现”。

### 当前暂不需要

多股票、技术位置止损、高频/Tick/Level 2、杠杆/做空/衍生品、复杂订单簿、多账户、分布式/GPU、数据库/Web/微服务、实盘、优化与 Walk Forward、事件总线。特定市场成交规则和公司行为处理需要按目标市场及数据口径另定优先级，不能永久视为无关。

## 6. ATR 检查结果

源码 `quant/indicators/` 只有 SMA，检索全部代码和测试未找到 TR/ATR。没有周期配置、None 暖机约定、策略调用或风险调用。

建议实现时明确以下合同，而不是直接把 ATR 混入 Engine：

```text
TR_t = max(High_t - Low_t, abs(High_t - Close_(t-1)), abs(Low_t - Close_(t-1)))
```

第一根无前收盘时，可定义 TR = High - Low。建议第一版选择并记录一种算法：例如 Wilder ATR，首个 ATR 为前 n 个 TR 的 SMA，其后 `ATR_t = ((n-1) × ATR_(t-1) + TR_t) / n`；也可选择 TR 的滚动 SMA，但两者结果不同，不能混称同一算法。周期为可配置正整数，未满周期返回 None。

所属模块：`quant/indicators/` 的纯函数/轻量实现，输入 Bar 或明确的价格序列，不读 CSV、不读账户、不发订单。由 Strategy 或实际新增的风险规则通过公开接口调用。只使用可见历史；开盘入场时不能用该执行 Bar 收盘后才知道的 ATR。

## 7. ATR Stop 检查结果

没有 stop_distance、stop_price、multiplier 字段/规则；没有每 Bar 止损判断，没有止损订单，也没有止损后的账户测试。

计划公式可为 `distance = 已知 ATR × multiplier`；ATR=2、multiplier=2 时距离=4；实际买入成交价 100 对应初始多头止损价 96。multiplier 必须有限且为正。Entry Price 建议采用实际成交价；当前 `average_price` 包含买入佣金，不能不加解释地当作实际成交价。

第一版推荐固定入场距离、不做 ATR 动态追踪。在 T 收盘观察的 ATR 用于 T+1 入场，入场成交后设置保护阈值。必须先决定止损时间语义：

- **预先存在的盘中保护止损**：已有阈值时，若 Open 已低于止损价，按 Open 加卖出滑点；否则 Low 触及止损价时，按约定阈值加卖出滑点。不能跳空低开仍假装按更好的止损价成交。
- **收盘确认止损**：T.Close 触发后 T+1.Open 卖出，规则更简单，但与盘中保护止损不同，风险可能更大，不能用 Low 触发却回填当日 Open。

上面是候选合同，当前均未实现。对第一套 ATR 风控策略优先采用明确的保护止损合同；如选择收盘止损，必须据此调整风险解释和验收样例。新 Stop 类型/入场当根是否激活、MA 退出与止损同时到期的优先级、末根处理必须一并定义。

止损阈值由实际需要的轻量风险规则维护，通过公开成交/账户快照更新；触发成交规则由 Broker/Execution 承担。Engine 只推进阶段和转交订单/Trade；Portfolio 仍唯一更新现金和数量。不得让 Strategy 或 Engine 直接扣款清仓。

## 8. Commission 检查结果

[commission.py](../quant/broker/commission.py) 已有 CommissionModel Protocol、PercentageCommission、FixedCommission。比例费率范围 `[0,1)`，固定费用有限非负；零费用可用 PercentageCommission(0)，无需为了类名再加空模型。

实际链路：Engine `_create_order` 调用 Broker 的含费可负担量 → Broker `execute` 在实际成交价上调用 `calculate` → Trade 保存 commission → Portfolio 买入扣 `price × quantity + commission`，卖出加 `price × quantity - commission` → 权益进入绩效。因此最终回测收益扣除了已发生的买卖佣金。

默认 Broker 和示例费率均为 0.0003；示例构造器明确传入模型。报价的多次费用计算没有重复扣款，最终每笔 Trade 只入账一次。固定模型是“每笔固定费用”，不是“最低佣金”；尚无卖出税费或按市场/方向不同的收费，不影响基础模型已实现的判断。

扩展模型需费用非负、随数量单调不减，以保证 Broker 二分可负担量有效；应为纯计算，不能在报价时产生扣款副作用。

## 9. Slippage 检查结果

[slippage.py](../quant/broker/slippage.py) 已有 NoSlippage、FixedSlippage、PercentageSlippage。百分比模型买入 `Open × (1+rate)`，卖出 `Open × (1-rate)`；固定模型买入加 amount、卖出减 amount。Broker 在报价及最终成交调用模型，Trade.price 是调整后价格。

Portfolio 使用实际 Trade.price 更新现金、含费成本和已实现盈亏，权益据此变化；不是只用于画图或输出。示例显式用 NoSlippage，意味着当前示例选择零滑点，不能据此判缺失；真实数据研究应增加非零滑点情景对比。

固定滑点导致卖出价非正时 Broker 会拒绝；无量能/价差/冲击模型、不要求成交价必须处于 Bar 高低区间，这是当前简化假设。新增报价模型应无状态且同参数可复现，避免定量报价和成交价不一致。

### 本次实际手算验证

通过 Engine 构造三根参考价格均为 10 的 Bar，初始 1000、比例仓位 100%、买卖佣金 1%、买卖百分比滑点 10%：

| 步骤 | 实际结果 |
|---|---|
| BUY | 下一根 Open 成交 90 股，实际价 11，手续费 9.9 |
| 买后现金 | `1000 - 90 × 11 - 9.9 = 0.1` |
| SELL | 再下一根 Open 卖 90 股，实际价 9，手续费 8.1 |
| 最终现金/权益 | `0.1 + 90 × 9 - 8.1 = 802`，持仓 0 |
| Total Return | `802 / 1000 - 1 = -19.8%` |

这是不落盘的审查验证，不是已经新增到仓库的回归测试。

## 10. 潜在回测正确性问题

### A. 已复现缺陷

**A1：比例预算的二进制浮点误差使整股数量少一股。**

- 位置：`quant/engine/backtest_engine.py:144-146`；`quant/portfolio/position_sizer.py:63-64`；`quant/broker/broker.py:28-47`。
- 复现：初始权益 100，比例 0.29，执行价 1，零佣金/滑点。Sizer 的 Decimal 路径给 29；Engine 计算 `100 * 0.29 = 28.999999999999996`，可负担量转 int 后为 28；实际 Trade 数量 28。
- 影响：偏离预期比例，非超支、非前视。现有测试只测 .1/.2/.5 等样例，没覆盖此端到端边界。
- 最小方向：统一比例预算与整股计算的精度合同；费用可负担量应以实际整数候选成本校验。不要简单加 epsilon 后向上取整，否则可能真的超支。

**A2：卖出容差留下微小负现金，绩效计算失败。**

- 位置：`quant/portfolio/portfolio.py:72-79`；`quant/analytics/metrics.py:30-32`。
- 复现：初始现金 1，先买 1 股@1、费 0，再卖 1 股@1、手续费 1.000000005。卖出验证允许余额高于 -1e-8，更新后 cash = -4.999999969612645e-9；清仓权益也为负，Analytics 拒绝“组合资产必须是有限非负数”。
- 影响：合法构造的 Trade 可破坏非负现金不变量；示例默认费用不易触发，但公开 Portfolio 接口支持这一输入。买入有近零归零，卖出缺对应处理。
- 最小方向：明确统一容差，拒绝实质资金不足并将允许范围内残差归零；校验失败不能改变数量、均价、盈亏或现金。

### B. 策略语义与扩展边界，不应混报成普遍缺陷

- **MA 状态不等于严格交叉**：`ma_cross.py:37-46`。手算 `[1,2,3,4,4,4]`、短2长3，首次就绪输出 BUY，最后相等输出 SELL。需要明确策略名称/口径，增加首次暖机、相等、重复调用测试，而不是未经选择更改既有策略行为。
- **拒单后不自动重试**：`_last_target` 记录市场状态，而非成交事实。实测初始5、买入日 Open10 不够一股，后续 Open1 可负担但仍同向时无新 BUY，账户持续空仓。这符合“状态改变才发意图”的实现；若目标是持续追踪目标仓位，后续应由订单/风险编排定义重试与止损后再入场规则，不让 Strategy 读取内部账户。
- **PositionSizer 接口不是风险接口**：只有 equity/price 和 position_ratio，Engine 又强制按比例预算。风险定仓不能只实现一个同名类便称完成；需要公开传递 stop_distance/risk_fraction，明确现金上限与风险额度的不同含义。
- **配置可变性**：修改 `FixedFractionPositionSizer.position_ratio` 会与内部 Decimal `_ratio` 分离；实测从 .2 修改为 .8 后 `calculate_quantity(1000,10)` 仍为20，公开 ratio 却为.8。当前没有运行时修改需求，推荐 P1 将配置明确为只读或受控同步，而非新增动态配置系统。
- **边界校验不统一**：MA 构造器不直接检查窗口为 int；OrderResult 未验证 FILLED 必须有 Trade、Trade.order_id 与结果一致；末根 PendingOrder 的意图标的/时间没有与当根 Bar 统一校验。当前内置流程产生的对象正常，自定义协作者接入前应补合同和失败测试，列 P1。

### C. 回测假设与数据风险

- Bar.datetime 只是时间戳，CSV 接受 ISO datetime，并不保证一天一根、交易日历完整或时区一致；Analytics 却每 Bar 当作交易日按252年化。日线教学可用，分钟线不能直接复用该年化口径。缺整天行情不等于字段缺失；未检测停牌/缺日。
- Volume 只校验非负，Broker 不用 Volume 决定能否成交；零量 Bar 也可成交。未模拟涨跌停无法成交、T+1、整手、限价/部分成交。若目标变为特定市场，应先明确规则再提升优先级，不将当前结果称为真实撮合。
- `stock_real.csv` 只有 OHLCV，没有来源、原始/复权口径、分红拆股元数据，单靠代码不能判断是否存在公司行为或数据层面的未来信息。真实研究前先核实；不要仅因日期排序正确就声称数据集完全无偏。
- 内置策略可见历史没有未来数据；Strategy 协议本身无法阻止用户自定义策略自行读取整份数据。也没有样本选择/参数筛选偏差检查。
- 年化与 Sharpe 是日线假设下的研究统计。最大回撤只看日终权益，不捕捉盘中下跌；末日权益不是强平净回款。
- MA 每 Bar 重算完整历史，总体接近 O(n²)，Engine/CSV 均全量加载。当前几百根日线不需流式/缓存重构，规模增长后再测性能。

## 11. 测试检查与实际验证

| 检查项 | 现有测试证据 | 覆盖评价 |
|---|---|---|
| 买入、Cash/Position、含费现金 | `test_broker_portfolio.py:14`、`test_position_sizer.py:53` | 有正常路径，缺直接精确均价/费用/数量组合金标 |
| 卖出、清仓回款 | `test_broker_portfolio.py:51`、`test_position_sizer.py:53` | 有，但使用零费用/零滑点 |
| 非法持仓/重复入账 | `test_broker_portfolio.py:32` | 实际只测超额卖出；名称虽含 duplicate，没有重复入账测试 |
| 资金不足/原子性/部分卖出 | 数量不足一股测试；部分费用预算测试 | 缺直接 apply_trade 资金不足、失败不改状态、部分卖出成本/盈亏 |
| 固定比例定仓 | `test_position_sizer.py` 7项 | 包含非法比例、整股、现金/费用上限；缺 .29 Engine 精度边界 |
| ATR、ATR Stop、风险定仓 | 无 | 功能与测试均缺失 |
| Commission | 比例买入、固定佣金可负担量、带成本集成 | 缺非零卖出费用、固定费买卖入账、精确成本闭环 |
| Slippage | 固定买入价、带固定滑点集成 | 缺百分比双方向、固定卖出价、无效价拒绝 |
| Maximum Drawdown | `test_engine_analytics.py:53` | 仅平坦曲线0；缺峰值跌落/初始损失/恢复/清零手算 |
| 年化/Sharpe | 同上平坦样例 | 缺非零收益、样本标准差、无风险利率、短序列金标 |
| 时间语义 | `test_engine_analytics.py:20` | 明确下一根 Open、末根过期、禁止重复 run；缺未来后缀不影响前缀结果性质测试 |
| Data/指标/策略 | `test_data_indicators_strategy.py` 5项 | 有乱序/重复/坏行/暖机/买卖；缺多类边界与默认5/20金标 |
| 完整集成 | `tests/integration/test_backtest.py` | 确认有 Trade、快照数、资产恒等式；不能证明精确成本/收益正确 |
| 图表 | `test_visualization.py` 2项 | 非交互后端、实际成交标记、权益曲线；不承担交易正确性证明 |

本次实际执行：

- `python -m pytest -q`：**26 passed in 6.75s**，完整现有套件。
- `ruff check .`、`mypy quant`：PowerShell 找不到命令，未完成检查。
- `python -m ruff check .`、`python -m mypy quant`：默认 Python 均报 No module named，对应依赖未安装；没有声称静态检查通过，也未安装依赖。
- PowerShell here-string 经 `python -` 执行临时验证：双向百分比滑点/佣金完整 Engine 闭环；非零回撤手算；MA 首次入场/相等退出；公开盈亏字段缺失；比例配置变更不同步；拒单不重试；A1/A2 缺陷复现。没有新增测试文件。
- 非零绩效样例：初始100、权益 `[120,90,108]` → 总收益8%、最大回撤-25%、Sharpe约3.05505；年化按当前3个交易日定义，极高数值只是短区间复合外推。
- 同一临时脚本调用 `run_example('data/stock_real.csv')`，未打开图窗：**31笔成交，最终权益146173.52279237，总收益46.1735%，年化20.7665%，最大回撤-18.0102%，Sharpe约0.85076**。这是当前整股实现的运行事实，非市场收益预测。
- `git diff --check`：报告生成前通过；报告完成后的检查见交付复核。未更改交易行为，故不新增业务 Change Record 或 CHANGELOG 项。

文档一致性发现：V0.1 TODO 的 Phase10 记载期末权益139307.19，历史 Change Record 记载146176.65，当前结果146173.52。前两者不能当作本次金标；当前整股规则及不同历史执行版本会影响结果。后续应记录每个数字的版本/数据/参数。README 的“不支持部分卖出”对 Engine 成立，但 Portfolio.apply_trade 实际可处理部分卖出；报告已区分模块能力。本次不改既有文档。

## 12. 架构扩展建议：最小修改

| 能力 | 正确归属 | 当前扩展点/需要最小调整 | 不应放的位置 |
|---|---|---|---|
| TR / ATR | `quant/indicators/` | 纯计算 + 暖机 + 参数 + 公开导出；消费领域行情 | CSVFeed、Portfolio、Engine 中的公式 |
| ATR 入场/信号条件 | `quant/strategy/` | 调用指标，输出交易意图和必要可见上下文 | 账户扣款/成交定价 |
| 风险金额与定仓 | `quant/portfolio/position_sizer.py` 或真实需要的轻量风险规则 | 最小扩展输入含止损距离/风险比例；将固定资金比例预算与风险预算区分 | Strategy 读写账户、Engine 写除法规则 |
| ATR Stop 阈值/退出政策 | 轻量风险/止损规则，新增时再创建实际模块 | 接收公开行情、实际成交和账户快照；固定入场距离、去重/失效处理 | Portfolio 产生信号、巨大 RiskManager 空壳 |
| 止损触发成交及跳空定价 | `quant/broker/` / 具体 Execution | 明确预先挂单语义与必要订单字段/类型，产出 Trade | Engine 实现撮合价、Strategy 同 Bar 回填成交 |
| Commission / Slippage | 已有 `quant/broker/` | 保留现有模型；先补测试，再按市场需要扩展 | 重写到 Strategy/Portfolio |
| 现金/持仓/盈亏入账 | `quant/portfolio/` | 公开只读快照、容差修复；只消费成交事实 | Broker 拥有账户状态 |

当前分层能够自然支持 `Indicator → Strategy → 实际风险规则/定仓 → Order → Broker → Portfolio`，但风险上下文和止损生命周期需要新增真实接口。不存在“只增加 ATR 函数，Engine 无需任何协作调整就能自动止损”的能力。

新增 Stop 订单会影响 OrderType、Broker 执行语义和 Engine 调度；应先说明原因、替代的收盘退出方案、迁移影响，再改文档/测试。保持旧 MA 默认行为和固定比例构造兼容；不要为了目标流程图预建 risk/base/config/事件总线。固定入场 ATR 止损无需做复杂追踪止损、多资产风险引擎或依赖注入容器。

## 13. P0 / P1 / P2 TODO 与完成标准

P0 分两类：**现有基础回测正确性必须补齐**（01—03）；**下一套带单笔风险控制策略必须形成的闭环**（04—06）。ATR 本身不是无止损 MA 回测的正确性前提；后者是学习目标扩展，须作为新阶段，不应把 V0.1 TODO 已完成状态改成“缺 ATR 所以未完成”。

### P0：当前必须优先处理

| TODO | 为什么需要 | 应修改模块 | 依赖 | 完成标准 | 需要增加的测试 |
|---|---|---|---|---|---|
| P0-01 修复比例预算精度 | 实际29%配仓可能少买一股 | `portfolio/position_sizer.py`、`engine/backtest_engine.py`，必要时 Broker 可负担整股边界 | 现有 Sizer、佣金报价、Portfolio | 权益100/比例.29/价1/零费实际买29；含费/现金上限仍不超支 | Engine 端到端 .29；整除/差一股边界；非零佣金和滑点；现金不足 |
| P0-02 统一现金残差与拒绝原子性 | 防止负现金破坏估值及绩效 | `portfolio/portfolio.py` | Trade 校验、Analytics 非负口径 | A2 合理拒绝或按统一容差归零；实质不足仍拒绝；失败不改状态 | 极小负残差卖出；实质费用不足；买入容差；超卖/重复成交原子性 |
| P0-03 补现有正确性金标并明确 MA/数据合同 | 通过26项不等于费用/回撤正确；避免教学理解错误 | `tests/unit/`、`tests/integration/`；README/architecture/V0.1 TODO 的必要说明 | 现有 MA→Broker→Portfolio→Analytics | 双向成本闭环、非零MDD/收益、真实5/20和前缀可见性可验证；所有历史结果注明基线；策略相等/首次就绪合同明确 | 本报告802闭环、含费均价、部分卖出/盈亏、重复Trade；峰值120跌90回撤-25%；初始损失/恢复/归零；默认5/20、相等、后缀变化不改前缀成交 |
| P0-04 实现 TR/ATR 纯指标 | 为风险距离提供可解释的波动率输入 | `quant/indicators/`、指标单测；同步范围文档 | Bar 的 H/L/C、SMA 暖机惯例 | 选择首根规则与 Wilder/SMA算法；周期可配；未就绪 None；Strategy/风险规则可公开调用 | 普通波动、向上/下跳空手算TR；首根；n=1/非法n/短历史/平价；ATR递推；追加未来数据不改过去值 |
| P0-05 基于止损距离的风险定仓 | 资金比例不等于允许亏损比例 | PositionSizer 的最小公开扩展、实际风险规则、Engine 只传上下文 | P0-01、ATR/已知stop distance、公开权益、Broker费用报价 | `floor(权益×risk_fraction/stop_distance)`，再以现金/实际成交成本裁量；风险比例可配；拒绝零/负距离、ATR未就绪；公式不写在Engine | 权益100000/风险1%/距离4→250股；不足现金降低量；整数/零距离/非法比例/缺ATR；跳空入场用执行价，不能用执行Bar未来ATR |
| P0-06 ATR Stop→卖单→成交→入账完整闭环 | 只有风险数量而没有实际止损，风险额度就无保护执行 | 实际轻量止损规则、Core 必要订单字段、Broker/Execution、Engine 阶段协作、Portfolio公开快照 | P0-04/05、成交记录、既有成本/账户 | ATR2×倍数2=距离4；入场100→Stop96；每Bar按已选时间合同检查，跳空按实际价，止损后持仓0且费用正确；退出去重/状态清理 | 未触发/等于阈值/Low触及/跳空低开/入场当根/末根；ATR不可用；非法multiplier；MA退出与Stop同根只卖一次；止损后账户和再入场政策 |

风险定仓的距离公式只约束计划价格风险；跳空、滑点和手续费可使实际净亏损超过该预算。第一版应明确成本是否纳入风险预算，至少保留含费现金上限，并测试超出风险预算的跳空情形，不能宣称“最大亏损被保证”。

### P1：完成第一套完整策略后实现

| TODO | 为什么需要 | 应修改模块 | 依赖 | 完成标准 | 需要增加的测试 |
|---|---|---|---|---|---|
| P1-01 公开已实现/未实现/组合净盈亏 | 当前只能看权益和内部累计，难解释收益来源 | Portfolio 只读快照、必要结果字段；Analytics报告 | Trade含费成本、P0资金不变量 | 含买入费成本口径清楚；浮盈亏=数量×(mark-均价)；闭环净盈亏与权益变化一致 | 加仓加权、部分卖出、清仓、双向佣金、亏损/盈利；无外部状态修改 |
| P1-02 已平仓交易统计与 Win Rate | 初学者需要理解每次进出结果，不应把BUY/SELL成交分别当胜负 | `quant/analytics/`，按需只读报告 | P1-01/Trade与退出记录 | 净盈亏扣成本；仅已平仓交易计入胜率；零交易/未平仓口径明确；Profit Factor可顺带但非阻塞 | 一赢一亏/零收益/无平仓/期末持仓；费用把毛盈利变净亏；部分退出配对合同 |
| P1-03 整理示例参数与配置一致性 | 当前要改函数内部才能切初始资金/窗口/成本；mutable ratio双份不一致 | 示例显式参数/简单配置对象、PositionSizer配置边界 | 现有构造器，P0-01 | 一处组装参数、默认兼容；ratio只读或同步更新；无复杂配置框架 | 默认与原行为一致；自定义资金/比例/滑点；非法参数早报错；ratio变更被拒或正确同步 |
| P1-04 可选固定股数/百分比止损 | 便于对照学过的两种基础规则，不必同时做很多风险算法 | PositionSizer实际输入合同、现有止损规则扩展 | P0-05/06接口稳定 | 固定股数仍受现金/成本限制；百分比止损复用同一成交与入账链路 | 固定10股/资金不足/非整股；百分比阈值/跳空/重复退出；不破坏ATR规则 |
| P1-05 数据溯源与研究基准 | 未知复权/来源时真实回测难解释 | Data文档/必要元数据；Analytics/示例只读基准 | CSV、Equity、实际数据来源信息 | 记录标的、来源、日线/复权/缺日口径；可选Buy&Hold与同成本比较；目标市场规则明确 | 缺交易日/零量处理；复权与现金分红避免双算；基准无前视/同费用；不填未来值 |
| P1-06 加固公开对象和自定义协作者合同 | 防止错误时间/标的/结果关联悄悄进入输出 | Core、Strategy构造器、Engine意图边界、Broker模型合同 | 既有领域对象和Protocol | 窗口类型早校验；信号时间/标的与当前观察一致；FILLED必须正确关联Trade；报价模型有限且可复现 | 非整数窗口；错标的/回填信号/末根错误意图；无Trade的FILLED、错order_id；坏模型结果 |

若研究目标明确为真实特定市场，P1-05 的数据口径和关键成交限制应提前至对应研究验收的 P0；本报告不在未知市场下猜测费率、税费和规则。

### P2：以后再实现

| TODO | 为什么需要/现在为何推迟 | 应修改模块 | 依赖 | 完成标准 | 需要增加的测试 |
|---|---|---|---|---|---|
| P2-01 多股票/多持仓与资金分配 | 比较资产和组合时有价值；当前单股足够 | Data同步、Portfolio多持仓、Engine多标的协作 | 单标的风控/账户稳定 | 同时持仓、缺行情估值与分配政策明确 | 时间错位、缺行情、标的隔离、共享现金上限 |
| P2-02 技术位置/追踪止损、止盈和复杂风控 | 扩展退出方式；先验证固定入场ATRStop | 风险规则/指标，Broker复用执行 | P0-06 | 阈值只能用已知行情，优先级清楚 | 阈值更新无前视、跳空、同Bar多条件、不重复平仓 |
| P2-03 优化/样本外/Walk Forward/多策略 | 策略研究成熟后再关注泛化；目前防止过度设计 | 独立研究/优化编排、Analytics | 可重建协作者、P1配置/基准 | 训练与测试隔离、参数选择可追溯 | 样本隔离、重复运行可复现、多策略资金/冲突合同 |
| P2-04 更真实订单与成交容量 | 大订单/其他市场才需要 | Core订单、Broker/Execution、市场数据 | 基础执行/止损合同 | 按目标市场支持限价、部分成交、成交量限制等 | 缺量、部分成交余额、撤单、不可成交日、成本分配 |
| P2-05 做空/杠杆/衍生品 | 改变账户和风险模型，当前学习阶段不需要 | Core、Portfolio、Broker、Risk | 多资产/风险稳定且有明确需求 | 保证金/借券/清算规则明确 | 强平、负暴露、保证金不足、费用与结算 |
| P2-06 事件总线/数据库/Web/实盘/高频/GPU | 只有真实场景或性能证据才增加 | 按场景新增基础设施/适配器 | 完整回测验收、目标市场合同；先Paper再实盘 | 不侵入Core/Strategy；事件/持久化/实盘语义可恢复 | 重复事件幂等、断线重连、历史与实时一致；性能基准与业务结果一致 |

## 14. 推荐实现顺序与交付复核

推荐下一步首先修复 **比例预算精度、卖出现金残差**，并补非零成本/回撤的端到端金标。这比重新实现已有手续费或滑点更有价值。

之后按依赖推进：

```text
P0-01/02 现有缺陷 → P0-03 测试与口径
  → P0-04 TR/ATR
  → 定义入场ATR/止损距离/执行时间合同
  → P0-05 风险定仓 + P0-06 ATR保护止损（共同验收）
  → P1 盈亏输出/胜率/简单配置/数据基准
  → 明确需要时才选 P2
```

风险定仓可先用手工止损距离完成纯计算单测；但在没有执行止损前，不能把这一阶段独立称为完成的风控策略。Commission/Slippage 继续使用现有 Broker 模型，不增加重复实现。

矩阵共 **53 项**：**✅ 已完整实现 32 项、⚠️ 部分实现 8 项、❌ 未实现 8 项、⏳ 当前暂不需要 5 项**。这些是检查项数量，不表示存在 53 个独立功能。部分实现不是未实现，暂不需要也不计入缺失数量。

交付复核：报告内 Markdown 链接及明确列出的现有代码/测试路径均存在；阶段依赖已核对，先修复现有基础、再补 ATR→风险定仓→止损共同验收，没有用尚不存在的模块当作现有依赖。`git diff --check` 通过；Git 状态仅新增 `docs/quant_framework_gap_analysis.md`，没有代码/配置/既有文档变更。

剩余风险：静态检查未完成；市场/数据来源与复权口径未验证；现有测试覆盖不足；两项已复现缺陷本次按要求未修复；ATR及止损语义仍需实现前具体设计。

本次无公共接口、依赖方向或核心架构变更，因此不修改 README、architecture、V0.1 TODO、CHANGELOG，也不创建业务 Change Record。未来执行 TODO 时按 AGENTS 要求同步相关文档和记录，P0扩展不能直接视为已完成能力。
