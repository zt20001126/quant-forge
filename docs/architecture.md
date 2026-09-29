# QuantForge V0.1 架构基线

本文记录当前仓库的真实实现。长期目标与版本演进见[架构设计与长期演进指南](Personal_Quant_Framework_架构设计与长期演进指南.md)；阶段清单见[V0.1 TODO](V0.1_TODO.md)。

## 当前实现范围

当前实现支持单标的日线 CSV、MA Cross、SMA 与 True Range/Wilder ATR、固定比例与风险比例整股仓位、可选 ATR 保护止损、市价/止损市价执行、佣金/滑点、单一多头 Portfolio、回测结果和基础绩效。ATR 可由 MA Cross 附加到买入意图，Engine 使用止损距离计算风险仓位并在买入成交后启用固定止损。Python 包实际位于仓库根目录 `quant/`，不是 `src/quant/`。不包含通用 RiskManager；资金不足、无效订单和禁止负持仓通过 Engine、Broker 及 Portfolio 的边界校验处理。

## 模块职责

| 模块 | 当前职责 | 明确不承担 |
|---|---|---|
| `quant.core` | Bar、OrderIntent、Order、OrderResult、Trade、Position、枚举及通用领域校验 | 文件读取、策略、成交、账户生命周期 |
| `quant.data` | DataFeed 协议；读取 CSV、校验 OHLCV、排序并产出 Bar | 指标、信号或账户状态 |
| `quant.indicators` | 简单移动平均、True Range 与 Wilder ATR 纯计算 | 数据读取、交易决策、账户状态 |
| `quant.strategy` | 消费当前 Bar 与截至当前的历史 Bar，产生目标仓位意图；可将 ATR 止损距离附加到买入意图 | 读取具体数据源、读取/修改账户、成交与费用 |
| `quant.risk` | 保存成交后生效的 ATR 固定止损价，并判断跳空/日内触发 | 账户状态、成交定价、策略信号、动态追踪止损 |
| `quant.broker` | 市价/止损市价订单执行、滑点应用、佣金计算、含费最大可买数量报价 | 策略决策及现金/持仓所有权 |
| `quant.portfolio` | 现金、单标的持仓、Trade 入账、账户估值；固定比例/风险比例整股数量 | 生成信号、决定成交价、持有止损状态 |
| `quant.engine` | 推进生命周期、协作公开接口、汇总 Trade/订单结果/权益快照 | MA 计算、撮合公式、佣金公式、绩效算法 |
| `quant.analytics` | 从 BacktestResult 计算收益、年化收益、最大回撤和 Sharpe | 交易循环或账户修改 |
| `quant.visualization` | 读取 Bar 序列与 BacktestResult，展示收盘价方向、成交点和权益曲线 | 修改回测结果、生成信号或更改账户 |
| `examples` | 组装协作者并展示结果 | 绕过公开边界实现交易规则 |

目前没有通用 RiskManager；V0.1 只包含当前确有调用链的 ATR 固定止损状态与风险定仓规则，不代表提供完整的交易风控系统。没有预建未使用的 `config`、事件总线或工厂模块。

## 依赖方向

```text
examples → engine + 具体实现
examples → visualization
engine → core + DataFeed/Strategy/PositionSizer 协议 + Broker + Portfolio + ATR Stop Policy
data / indicators / strategy / broker / portfolio / risk → core
analytics → engine 的只读结果模型 + 标准库
visualization → core.Bar + engine.BacktestResult + Matplotlib
```

`core` 不依赖其他业务模块或第三方行情实现。Strategy 依赖领域 Bar/OrderIntent 与指标函数，不依赖 CSV、Broker 或 Portfolio。Engine 通过 DataFeed/Strategy 协议和 Broker/Portfolio 的公开方法编排。Broker 与 Portfolio 之间不互调：Broker 返回 Trade，Engine 将成交交给 Portfolio。Analytics 只接受结果对象；Visualization 只读取行情与回测结果。

V0.1 只有一个 Broker 实现，Engine 对其具体类型 `SimulatedBroker` 有显式依赖；目前这不构成抽象缺口，不为尚不存在的第二实现增加额外接口层。

## 领域对象

- `Bar`：冻结的 OHLCV 值对象，验证标的、时间、正价格、非负成交量与 OHLC 关系。
- `OrderIntent`：策略发出的方向目标，V0.1 仅为 0（空仓）或 1（多头），实际比例由仓位器决定；可携带买入保护止损距离。
- `Order`：执行数量、方向、类型和执行时间已确定的市价单或止损市价单。
- `OrderResult`：只有 FILLED 可且必须携带 Trade，且关联订单 ID 必须一致；拒绝结果保留具体原因。
- `Trade`：Broker 生成的不可变成交记录，包含订单关联、成交价/量、佣金及信号/执行时间。
- `Position`：Portfolio 持有的可变多头持仓状态；市值在估值时按价格计算。
- `EquitySnapshot` / `BacktestResult`：只读回测输出，供展示与 Analytics 使用。

## 指标计算

`quant.indicators.true_range(bars)` 接受同一标的、按时间严格递增的 Bar 序列。首根 Bar 没有前收盘价，TR 定义为 `High - Low`；之后取 `max(High - Low, abs(High - PreviousClose), abs(Low - PreviousClose))`。`average_true_range(bars, period)` 使用 Wilder 算法：首个 ATR 为前 `period` 个 TR 的简单平均，随后 `ATR_t = ((period - 1) × ATR_(t-1) + TR_t) / period`。暖机期返回 `None`。MA Cross 的 SMA 仅计算所需窗口，只有新的保护入场意图需要计算 ATR；ATR 未暖机或为零时保持先前目标并延迟入场。ATR 距离基于当前及过去数据，不含未来行情。

## 生命周期和时间语义

```text
读取并校验所有 Bar
  → 先检查已有止损是否被 Open 跳空触发
  → 对当前 Bar 开盘时到期的上根信号按 Open 估值权益，并按固定比例或风险预算及滑点报价定量
  → Broker 应用成交参考价、滑点和佣金并生成 Trade / 拒绝结果
  → Portfolio 对 Trade 入账
  → 检查活动止损是否被当前 Bar Low 触发并执行止损市价单
  → 按当前 Bar Close 记录 EquitySnapshot
  → Strategy 观察当前完整 Bar 并产生后续意图
  → 最后一根 Bar 的新意图记为 EXPIRED_NO_NEXT_BAR
  → BacktestResult → Analytics
```

Signal Time 是策略观察到完整 Bar 的时点；Execution Time 必须晚于 Signal Time。T 日 Close 形成的信号最早在下一根可用 Bar 的 Open 执行。Engine 在执行 Bar 到达后才根据 Open 估值的账户权益、仓位比例和滑点报价计算整股买入数量，再以仓位额度和可用现金为上限调用 Broker 的含佣金可负担数量逻辑，不用未来价格。仓位公式为 `floor(Equity × PositionRatio / Price)`；手续费计入比例额度，任何浮点余量均向下取整。卖出意图按 Portfolio 当前全部持仓生成，不走买入仓位器。Broker 对成交 Trade 只记录一次实际佣金。估值发生在当根交易处理后，因此当日快照含开盘成交后的收盘持仓市值。

末根 Bar 产生的信号因无下一根执行机会而过期，不得按末日 Close 回填成交。买入意图没有可确定数量，`PendingOrder.quantity` 为 `None`；卖出意图记录待卖出的当前持仓数量。默认 `FixedFractionPositionSizer` 比例为 1.0，以兼容原有 Engine 默认满仓行为。可注入 `RiskBasedPositionSizer`，数量为 `floor(Equity × RiskFraction / StopDistance)`，买入预算再受可用现金、佣金和滑点后报价限制；风险定仓要求意图包含有效止损距离。ATR 止损在买入成交后以实际成交价减距离锚定，仅支持固定止损。日线若 Open 跌穿止损按 Open 成交参考价，若 Open 高于止损而 Low 触及则按止损价；Broker 后续应用卖出滑点和佣金。日线 OHLC 不揭示盘中路径，跳空与费用可能导致实际损失超过名义风险预算。

Engine 立即校验策略意图的标的与当前 Bar 时间，末根意图也不能跳过校验。自定义策略的到期 BUY 若在跳空止损清仓后形成新仓，新仓须接受当前 Low 的保护止损检查；旧仓止损被拒绝且未发生新买入时，同根不重复提交该止损。Engine 的两阶段止损共用提交路径，订单不能形成时记录具体拒绝原因。库通过标准 logging 输出可选生命周期与拒绝诊断，不配置全局 handler。

仓位比例为只读配置，避免公开比例与 Decimal 计算值不一致。Broker 的零现金报价返回零，负现金、非有限值及非法价格抛出 ValueError；执行阶段非法价格/费用作为拒绝结果输出。保护性实际成交价必须能形成正止损价，校验成功后才允许入账。成本模型报价仍须满足费用非负、随数量单调不减的约定。

## 账户与绩效约束

- 买入现金变化为 `cash -= price × quantity + commission`；持仓加权均价使用含费成本。
- 卖出现金变化为 `cash += price × quantity - commission`；不得卖出超过持仓的数量。
- 股数严格校验，无超卖容差；底层允许小数股与部分卖出，任何正残余持仓保留成本和市值。现金独立使用 `CASH_ROUNDING_TOLERANCE=1e-8`，仅将容差内负现金归零。计算结果须有限，失败不得部分更新账户。
- 估值为 `portfolio_value = cash + quantity × mark_price`。
- 初始资金作为收益与回撤的起始值；年化收益按 252 个交易日复合年化。
- 最大回撤相对包含初始资金在内的历史权益峰值计算并以负数表示。
- Sharpe 使用日超额收益样本标准差并按 252 日年化；默认无风险年利率为零。
- 绩效遇到无法表示的年化或 Sharpe 数值时抛出明确 ValueError，不返回非有限指标。

这些是假设明确的研究指标，不构成对真实市场成交或收益的保证。

## 可视化

`quant.visualization` 是独立展示层，不修改交易数据或账户状态。`plot_backtest(bars, result)` 提供收盘价、实际成交点和权益的 Matplotlib 静态图；`plot_interactive_backtest` 提供共享时间轴的价格、权益和回撤 Plotly 图，并在价格悬停中显示 Bar 的 OHLCV、在成交点显示 Trade 已保存的成交价、数量、佣金和信号时间。指标与逐日止损价只能由调用方显式提供；当前 Strategy/BacktestResult 不暴露这些逐日序列。Trade 不独立保存滑点金额，故图表仅说明成交价已包含滑点影响，不估算滑点值。

## 测试与工具

测试放在 `tests/unit/` 和 `tests/integration/`，通过 pytest 发现；行为基准包含非法数据、指标暖机、策略信号、成交成本、账户不变量、下一根 Open 执行、末根信号过期和 CSV 到绩效结果的集成流程。新增边界回归覆盖零 ATR、新仓止损、超卖、残余持仓、非法模型输出、订单结果一致性与绩效溢出。mypy 覆盖 quant/examples/tests 并要求函数注解；GitHub Actions 使用 Python 3.10 检查。开发工具由 `pyproject.toml` 的 `dev` 依赖提供：pytest、ruff、mypy。标准命令见 README；CI 的实际通过状态以执行记录为准。

## 已知范围边界

当前仅有单标的日线、CSV、MA Cross、开仓市价单与保护性止损市价单、多头账户和固定/风险比例整股仓位计算；止损仅支持 ATR 固定保护止损，不含追踪止损、分批退出或通用 RiskManager。可视化提供静态与交互式回测研究图，不包含实时行情。没有复权/公司行为处理、多资产、做空、杠杆、优化、Walk Forward、事件驱动、数据库或实盘能力。新增或变更上述架构边界时，先说明原因与迁移影响，再同步本文件、测试和 V0.1 TODO。
