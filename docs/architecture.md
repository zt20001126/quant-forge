# QuantForge V0.1 架构基线

本文记录当前仓库的真实实现。长期目标与版本演进见[架构设计与长期演进指南](Personal_Quant_Framework_架构设计与长期演进指南.md)；阶段清单见[V0.1 TODO](V0.1_TODO.md)。

## 当前实现范围

V0.1 支持单标的日线 CSV、MA Cross、目标仓位意图、市价执行、佣金/滑点、单一多头 Portfolio、回测结果和基础绩效。Python 包实际位于仓库根目录 `quant/`，不是 `src/quant/`。项目没有单独的 `risk/` 或 `config/` 包，也不包含 RiskManager；资金不足、无效订单和禁止负持仓通过 Engine 的执行定量、Broker 及 Portfolio 的边界校验处理。

## 模块职责

| 模块 | 当前职责 | 明确不承担 |
|---|---|---|
| `quant.core` | Bar、OrderIntent、Order、OrderResult、Trade、Position、枚举及通用领域校验 | 文件读取、策略、成交、账户生命周期 |
| `quant.data` | DataFeed 协议；读取 CSV、校验 OHLCV、排序并产出 Bar | 指标、信号或账户状态 |
| `quant.indicators` | 简单移动平均计算 | 数据读取、交易决策 |
| `quant.strategy` | 消费当前 Bar 与截至当前的历史 Bar，产生目标仓位 OrderIntent | 读取具体数据源、读取/修改账户、成交与费用 |
| `quant.broker` | 订单执行、滑点应用、佣金计算、含费最大可买数量报价 | 策略决策及现金/持仓所有权 |
| `quant.portfolio` | 现金、单标的持仓、Trade 入账、账户估值 | 生成信号、决定成交价 |
| `quant.engine` | 推进生命周期、协作公开接口、汇总 Trade/订单结果/权益快照 | MA 计算、撮合公式、佣金公式、绩效算法 |
| `quant.analytics` | 从 BacktestResult 计算收益、年化收益、最大回撤和 Sharpe | 交易循环或账户修改 |
| `quant.visualization` | 读取 Bar 序列与 BacktestResult，展示收盘价方向、成交点和权益曲线 | 修改回测结果、生成信号或更改账户 |
| `examples` | 组装协作者并展示结果 | 绕过公开边界实现交易规则 |

目前没有独立风险管理阶段；V0.1 的风险边界是明确的基础不变量，不代表提供可配置的交易风控系统。没有预建未使用的 `risk`、`config`、事件总线或工厂模块。

## 依赖方向

```text
examples → engine + 具体实现
examples → visualization
engine → core + DataFeed/Strategy 协议 + Broker + Portfolio
data / indicators / strategy / broker / portfolio → core
analytics → engine 的只读结果模型 + 标准库
visualization → core.Bar + engine.BacktestResult + Matplotlib
```

`core` 不依赖其他业务模块或第三方行情实现。Strategy 依赖领域 Bar/OrderIntent 与指标函数，不依赖 CSV、Broker 或 Portfolio。Engine 通过 DataFeed/Strategy 协议和 Broker/Portfolio 的公开方法编排。Broker 与 Portfolio 之间不互调：Broker 返回 Trade，Engine 将成交交给 Portfolio。Analytics 只接受结果对象；Visualization 只读取行情与回测结果。

V0.1 只有一个 Broker 实现，Engine 对其具体类型 `SimulatedBroker` 有显式依赖；目前这不构成抽象缺口，不为尚不存在的第二实现增加额外接口层。

## 领域对象

- `Bar`：冻结的 OHLCV 值对象，验证标的、时间、正价格、非负成交量与 OHLC 关系。
- `OrderIntent`：策略发出的目标仓位，V0.1 仅为 0 或 1，并保留信号时间。
- `Order`：执行数量、方向、类型和执行时间已确定的市价单。
- `OrderResult`：成交或拒绝状态；成功成交时携带 Trade。
- `Trade`：Broker 生成的不可变成交记录，包含订单关联、成交价/量、佣金及信号/执行时间。
- `Position`：Portfolio 持有的可变多头持仓状态；市值在估值时按价格计算。
- `EquitySnapshot` / `BacktestResult`：只读回测输出，供展示与 Analytics 使用。

## 生命周期和时间语义

```text
读取并校验所有 Bar
  → 对当前 Bar 开盘时到期的上根信号按 Open 定价和定量
  → Broker 应用滑点并生成 Trade / 拒绝结果
  → Portfolio 对 Trade 入账
  → 按当前 Bar Close 记录 EquitySnapshot
  → Strategy 观察当前完整 Bar 并产生后续意图
  → 最后一根 Bar 的新意图记为 EXPIRED_NO_NEXT_BAR
  → BacktestResult → Analytics
```

Signal Time 是策略观察到完整 Bar 的时点；Execution Time 必须晚于 Signal Time。T 日 Close 形成的信号最早在下一根可用 Bar 的 Open 执行。Engine 在执行 Bar 到达后才根据 Open、佣金/滑点报价和可用现金定量，不用未来价格；Broker 对真正成交生成的 Trade 只记录一次实际佣金。估值发生在当根交易处理后，因此当日快照含开盘成交后的收盘持仓市值。

末根 Bar 产生的信号因无下一根执行机会而过期，不得按末日 Close 回填成交。买入意图没有可确定数量，`PendingOrder.quantity` 为 `None`；卖出意图记录待卖出的当前持仓数量。

## 账户与绩效约束

- 买入现金变化为 `cash -= price × quantity + commission`；持仓加权均价使用含费成本。
- 卖出现金变化为 `cash += price × quantity - commission`；不得卖出超过持仓的数量。
- 估值为 `portfolio_value = cash + quantity × mark_price`。
- 初始资金作为收益与回撤的起始值；年化收益按 252 个交易日复合年化。
- 最大回撤相对包含初始资金在内的历史权益峰值计算并以负数表示。
- Sharpe 使用日超额收益样本标准差并按 252 日年化；默认无风险年利率为零。

这些是假设明确的研究指标，不构成对真实市场成交或收益的保证。

## 可视化

`plot_backtest(bars, result)` 使用独立展示层绘图。价格面板按每日 Close 相对前一日的变化标注涨跌，并按 Trade 的实际执行时间和成交价标出买入/卖出；权益面板展示每日组合价值。绘图不改变交易数据或账户状态。示例在打印摘要后弹出 Matplotlib 窗口。

## 测试与工具

测试放在 `tests/unit/` 和 `tests/integration/`，通过 pytest 发现；行为基准包含非法数据、指标暖机、策略信号、成交成本、账户不变量、下一根 Open 执行、末根信号过期和 CSV 到绩效结果的集成流程。开发工具由 `pyproject.toml` 的 `dev` 依赖提供：pytest、ruff、mypy。标准命令见 README。

## 已知范围边界

当前仅有单标的日线、CSV、MA Cross、市价单和多头账户；可视化仅支持回测结果的静态研究图，不包含交互式图表或实时行情。没有复权/公司行为处理、RiskManager、多资产、做空、杠杆、优化、Walk Forward、事件驱动、数据库或实盘能力。新增或变更上述架构边界时，先说明原因与迁移影响，再同步本文件、测试和 V0.1 TODO。
