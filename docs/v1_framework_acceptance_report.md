# V1 基础量化框架可用性验收报告

验收日期：2026-09-29。业务代码基线：`30f6a80`（ATR 风险定仓与保护止损），包版本 `0.1.0`。开始验收时 Git 工作区干净。

> 本文保留上述基线的验收记录。后续代码质量审查补充发现零 ATR、同日止损后重入及小数股超卖边界问题，已经由[质量整改记录](changes/2026-09-29-005-quality-and-boundary-hardening.md)对应的修复和正式回归测试处理；当前质量检查与验证结果以该增量记录为准。

**结论：通过基础可用性验收，可作为单标的、多头、日线的个人学习与研究回测框架使用。** 本报告的“V1”是用户给出的基础能力验收标准，不表示发布 V1.0，也不要求长期指南中的 Paper Trading。A—L 条件均满足当前限定范围，未发现阻塞基础使用的业务问题。手续费、滑点、仓位与 ATR 止损均进入实际成交和账户链路。

结论有范围：不保证真实市场可成交、不处理复权与公司行为，止损损失也不保证等于风险预算。公开结果缺少直接的已实现/未实现盈亏字段；这些属于输出完善项，账户盈亏已经过手算核对。ruff/mypy 因当前解释器未安装而未验证，不能把 pytest 通过等同于这些检查通过。

本次仅新增此报告、[正式验收测试](../tests/integration/test_v1_acceptance.py)及[变更记录](changes/2026-09-29-004-v1-framework-acceptance.md)，未修改业务代码、既有测试预期、接口、架构或版本号。

## 1. 当前框架架构

按要求先读[长期指南](Personal_Quant_Framework_架构设计与长期演进指南.md)，再读[当前架构](architecture.md)、[V0.1 TODO](V0.1_TODO.md)，随后检查 [AGENTS](../AGENTS.md)、[README](../README.md)、[项目配置](../pyproject.toml)、全部 `quant/` Python 源码及包导出、全部正式测试、示例、行情和既有变更文档。旧缺口报告记录的是旧提交，未以其中“ATR 未实现”等历史结论判断本次状态。

实际包位于根目录 `quant/`，不是 `src/quant/`：

| 模块 | 当前职责与真实边界 |
|---|---|
| `core` | Bar、OrderIntent、Order、OrderResult、Trade、Position 及校验；不依赖行情库或绘图库 |
| `data` | DataFeed 协议及 CSVDataFeed，校验/排序后输出领域 Bar |
| `indicators` | SMA、TR、Wilder ATR；纯历史序列计算 |
| `strategy` | MA Cross 输出目标 0/1，可给买入附加 ATR 距离；不访问账户 |
| `portfolio/position_sizer.py` | 固定比例、风险比例整股数量及分配预算 |
| `risk` | AtrStopPolicy 固定止损状态、跳空与 Low 触发；无通用 RiskManager |
| `broker` | 市价/保护止损执行、滑点、佣金、可负担数量报价；无账户状态 |
| `portfolio` | 现金与持仓唯一所有者，Trade 入账与估值 |
| `engine` | 信号/订单/止损生命周期与结果汇总 |
| `analytics` | 总收益、年化收益、最大回撤、Sharpe；不参与交易 |
| `visualization` | 只读结果绘图；不改变成交与账户 |
| `examples` | 参数与协作者组装，输出摘要与图表 |

没有独立 `config/` 包；参数经构造函数传入，示例集中组装。不把没有空模块当作缺陷。源码导入方向检查未发现循环依赖、Strategy 访问 Portfolio、Broker 保存现金、Portfolio 生成信号或 Engine 重写指标/费用公式。

## 2. 完整数据流

```text
CSVDataFeed.__iter__ → 校验/排序后的 Bar
  → Engine 将已完成的历史前缀及当前 Bar 交给 Strategy.on_bar
  → SMA 判断目标 + 可选 Wilder ATR × multiplier
  → OrderIntent（signal_time、目标、止损距离）
  → 下一根 Bar Open 到达
  → Portfolio.mark_to_market(Open) + Broker.quote(BUY, Open)
  → PositionSizer.calculate_quantity / allocation_budget
  → Broker.max_affordable_integer_quantity（现金、额度、佣金限制）
  → Order → Broker.execute（参考价 → 滑点成交价 → 佣金）
  → Trade → Portfolio.apply_trade（现金、数量、含费成本）
  → 买入后 activate(实际成交价 − ATR 距离)
  → Stop Trigger → 全仓 STOP_MARKET → 同一 Broker 成本链 → Portfolio 平仓
  → 每根 Close 的 EquitySnapshot → BacktestResult → calculate_performance
```

同根 Bar 的实际顺序为：已有止损的 Open 跳空触发 → 上根待执行意图在 Open 执行 → 活动止损的 Low 触发（含刚买入的保护止损）→ Close 估值 → 当前完整 Bar 产生后续信号。正常 SELL 若已在 Open 平仓，会清除止损，不再按当天 Low 重复卖出。末根新信号没有执行机会，仅记录 `EXPIRED_NO_NEXT_BAR`。

市场参考价是 Open 或触发止损价；Order 保存数量、执行时间和可选触发价，普通市价单不预设限价；Trade.price 是加滑点后的真实模拟成交价。止损的 `signal_time` 沿用买入保护意图时间，不是精确的盘中触发时刻。

## 3. 功能验收矩阵

状态：✅ 当前范围完整实现；⚠️ 部分实现；❌ 未实现；⏳ 本次基础标准暂不需要。测试列的文件名均位于 `tests/unit/`，注明 integration 的除外。

| 功能 | 状态 | 代码位置 | 测试 | 是否阻塞 V1 | 问题 |
|---|---|---|---|---|---|
| Historical Data / OHLCV | ✅ | [csv_feed.py](../quant/data/csv_feed.py)，[bar.py](../quant/core/bar.py) | `test_data_indicators_strategy.py`；integration `test_v1_acceptance.py` | 否 | 空值/NaN/Inf 拒绝，乱序排序、重复时间拒绝；不自动填充缺失日 |
| MA / SMA | ✅ | [moving_average.py](../quant/indicators/moving_average.py) | `test_data_indicators_strategy.py`；新手算用例 | 否 | 窗口未满为 None；没有其他均线算法 |
| TR / Wilder ATR | ✅ | [average_true_range.py](../quant/indicators/average_true_range.py) | `test_average_true_range.py`；新手算用例 | 否 | 首根 TR=High−Low；ATR 首值为周期 TR 均值 |
| Strategy / BUY / SELL / HOLD | ✅ | [ma_cross.py](../quant/strategy/ma_cross.py) | `test_data_indicators_strategy.py`；新完整交易 | 否 | SMA 短线>长线为 1，否则为 0；无变化返回空列表表示 HOLD |
| Signal | ✅ | [order.py](../quant/core/order.py) `OrderIntent` | `test_core.py`；`test_engine_analytics.py` | 否 | 目标 1/0 是持仓方向；最终比例由仓位器控制 |
| 固定比例 Position Sizing | ✅ | [position_sizer.py](../quant/portfolio/position_sizer.py)，Engine `_create_order` | `test_position_sizer.py` | 否 | 整股向下取整，含费用总投入受比例预算与现金限制 |
| 风险比例 Position Sizing | ✅ | 同上 `RiskBasedPositionSizer` | `test_position_sizer.py`；integration 新四场景 | 否 | 距离缺失拒绝；名义风险不含跳空、滑点及佣金 |
| Order → Execution | ✅ | [backtest_engine.py](../quant/engine/backtest_engine.py)，[broker.py](../quant/broker/broker.py) | `test_engine_analytics.py`；integration 新优先级用例 | 否 | 市价与保护止损市价；不模拟成交量容量 |
| Slippage | ✅ | [slippage.py](../quant/broker/slippage.py)，Broker `execute` | `test_broker_portfolio.py`；新四场景 | 否 | 无/固定/比例模型均有真实代码；非零固定滑点闭环实测 |
| Commission | ✅ | [commission.py](../quant/broker/commission.py)，Portfolio `apply_trade` | `test_broker_portfolio.py`；新四场景 | 否 | 按实际成交金额比例或每笔固定费用计费并扣现金 |
| Position / Entry Cost | ✅ | [position.py](../quant/core/position.py)，[portfolio.py](../quant/portfolio/portfolio.py) | `test_core.py`；`test_broker_portfolio.py`；新重放用例 | 否 | average_price 为含买入佣金成本，不是裸成交价 |
| Cash / Market Value / Portfolio Value | ✅ | Portfolio `apply_trade` / `mark_to_market` | 既有账户测试；新现金不变量、拒绝原子性用例 | 否 | 禁止超额买入/卖出，重复 Trade 拒绝 |
| Realized / Unrealized PnL 输出 | ⚠️ | Position.realized_pnl；AccountSnapshot.average_price | 新重放核对含费成本、未实现损益、平仓现金损益 | 否 | 已实现值内部维护，未实现值可推导；公开 Snapshot/Result 未直接暴露两者 |
| ATR Stop Loss | ✅ | [atr_stop.py](../quant/risk/atr_stop.py)，Engine，Broker | `test_broker_portfolio.py`；integration 既有保护止损及新三止损场景 | 否 | 固定止损非追踪；入场当天也可触发 |
| 通用 RiskManager | ⏳ | 无；现有风控由边界不变量与固定止损承担 | 订单/账户/风险定仓测试 | 否 | 不因未实现通用风控而判失败 |
| Equity Curve | ✅ | [models.py](../quant/engine/models.py)，Engine `run` | `test_engine_analytics.py`；integration；图表测试 | 否 | 每根 Bar 处理后按 Close 估值，末日持仓不强平 |
| Total Return / Maximum Drawdown | ✅ | [metrics.py](../quant/analytics/metrics.py) | 新非平坦序列和完整交易手算；既有基准测试 | 否 | 初始本金参与峰值；回撤为负数 |
| Annualized Return / Sharpe | ✅ | 同上 | 新非平坦序列逐公式核对 | 否 | 252 日口径、样本标准差；极短区间年化解释价值有限 |
| Win Rate / Profit Factor | ⏳ | 无 | 无 | 否 | 未实现，不是基础通过条件 |
| Config / 可运行示例 | ✅ | 构造参数；[ma_cross_backtest.py](../examples/ma_cross_backtest.py) | README 原命令实跑 | 否 | 默认示例使用 MA5/20、不启用 ATR，需显式组装保护策略与风险仓位器 |

### A—L 客观依据

| 条件 | 判断 | 对应代码与实验证据 |
|---|---|---|
| A 加载历史数据 | 满足 | CSVDataFeed；实际完整加载 507 根，2019-01-02 至 2021-01-29；非法 CSV 正式测试 |
| B 计算指标 | 满足 | SMA/TR/ATR 纯函数；Wilder 种子/递推正式测试，人工行情信号日 SMA 与 ATR 手算 |
| C 产生交易信号 | 满足 | MACrossStrategy.on_bar；正常案例第 4 日 BUY，第 7 日 SELL；既有信号变化测试 |
| D 计算仓位 | 满足 | 两种 PositionSizer + Engine；风险 100/距离 3 → 33 股，现金含费上限 81 股 |
| E 订单并模拟成交 | 满足 | Engine `_create_order` → Broker.execute → Trade；第 5/8 日成交，成交时间晚于信号 |
| F 成本影响资产 | 满足 | Broker 成交价 12.1/9.9，佣金 3.993/3.267，Portfolio 最终现金 920.14 |
| G Portfolio 正确更新 | 满足 | 买后现金 596.707、33 股、均价 12.221；卖后 0 股；新拒绝/重复入账测试保持账户不变 |
| H 止损闭环 | 满足 | ATR 距离 3，止损 9.1；盘中/跳空/买入当天止损全部经成本链平仓，无残余持仓 |
| I Equity Curve | 满足 | 10 根人工行情对应 10 个 Close 快照；507 根示例对应 507 个快照 |
| J 基础绩效 | 满足 | calculate_performance；收益 −7.986%，回撤 −10.292120459%；独立非平坦序列核对 |
| K 核心测试通过 | 满足 | 基线 46/46；新增 10 项后完整 56/56，无失败、跳过或 warning |
| L 人工交易核对 | 满足 | 本报告第 6 节；正式 `test_manual_round_trip` 四个参数场景，断言使用独立手算值 |

## 4. 自动化测试结果

环境：Windows、Python 3.11.5、pytest 8.3.4、pluggy 1.6.0，pytest 插件 anyio 3.5.0。

| 实际命令 / 阶段 | Tests | Passed | Failed | Skipped | Warning | 结果 |
|---|---:|---:|---:|---:|---:|---|
| `python -m pytest -ra`（基线） | 46 | 46 | 0 | 0 | 0 | 0.79s，通过 |
| `python -m pytest -ra`（最终） | 56 | 56 | 0 | 0 | 0 | 0.75s，通过 |
| `python -m ruff check .` | — | — | — | — | — | 无法运行：`No module named ruff` |
| `python -m mypy quant` | — | — | — | — | — | 无法运行：`No module named mypy` |
| `git diff --check` | — | — | — | — | — | 通过；新增文件另做链接/语法核对 |

新增正式测试 `tests/integration/test_v1_acceptance.py` 可由统一 pytest 发现，共 10 项：人工完整交易四场景、非零绩效、未来后缀不改变信号前缀、账户拒绝原子性、连续 BUY 不加仓、待卖信号与跳空/盘中止损的优先级两场景。没有将临时 trace 脚本算作正式覆盖。

验收中首次人工 fixture 用连续的 12 收盘，导致第 6 日短长均线相等，按真实规则提早退出；该轮新增测试 6 通过、1 失败。原因是人工行情设计误将“相等”当作继续持有，并非框架账务失败。随后把第 6 日 Close 设计为 13，维持该日严格多头并让第 7 日发生下穿，保留原定第 8 日卖出价格、费用、最终现金预期；重新手算第 6 日峰值后通过。未修改已有测试、未改业务规则来取得通过。

覆盖复核：Indicator/ATR/Strategy/Position Sizing/BUY/SELL/Commission/Slippage/Portfolio/Position/Stop Loss/Maximum Drawdown/Engine 都有正式测试。既有最大回撤测试主要是零回撤，新增真实上涨后回撤序列弥补这一不足。尚未穷举所有第三方扩展模型、极端数值、Python 3.8 环境以及 GUI 交互。

## 5. 最小回测结果

使用真实 CSVDataFeed、MACrossStrategy、RiskBasedPositionSizer、SimulatedBroker、Portfolio 和 Analytics。10 根人工 OHLCV 如下；交易日用顺序日期表示，不验证交易所日历。

配置：初始现金 1000；MA(2,3)；ATR period=1、multiplier=1；风险比例 10%；固定滑点每股 0.1；佣金率 1%。较大的演示费用只为方便手算，不代表市场费率建议。

| 日 / 2024-01 | Open | High | Low | Close | Volume |
|---|---:|---:|---:|---:|---:|
| 01 | 10 | 11 | 9 | 10 | 100 |
| 02 | 10 | 11 | 9 | 10 | 100 |
| 03 | 10 | 11 | 9 | 10 | 100 |
| 04 | 12 | 13 | 11 | 12 | 100 |
| 05 | 12 | 13 | 11 | 12 | 100 |
| 06 | 13 | 14 | 12 | 13 | 100 |
| 07 | 11 | 12 | 10 | 11 | 100 |
| 08 | 10 | 11 | 9 | 10 | 100 |
| 09 | 10 | 11 | 9 | 10 | 100 |
| 10 | 10 | 11 | 9 | 10 | 100 |

正常策略卖出的完整记录：

| 时点 | 信号 / 成交 | Cash | Quantity | Close 市值 | Portfolio Value |
|---|---|---:|---:|---:|---:|
| 第 1—3 日 | 暖机/空仓 | 1000 | 0 | 0 | 1000 |
| 第 4 日收盘 | BUY 意图，距离 3；尚未成交 | 1000 | 0 | 0 | 1000 |
| 第 5 日 Open | `order-000001` BUY 33；参考 12 → 成交 12.1；佣金 3.993 | 596.707 | 33 | 396 | 992.707 |
| 第 6 日收盘 | HOLD | 596.707 | 33 | 429 | 1025.707 |
| 第 7 日收盘 | SELL 意图；尚未成交 | 596.707 | 33 | 363 | 959.707 |
| 第 8 日 Open | `order-000002` SELL 33；参考 10 → 成交 9.9；佣金 3.267 | 920.14 | 0 | 0 | 920.14 |
| 第 9—10 日 | 空仓 | 920.14 | 0 | 0 | 920.14 |

实际输出：总收益 −7.986%；最大回撤 −10.292120459351439%；年化收益 −87.72225674772961%；Sharpe −4.75324747835746。10 日的年化值仅验证公式，不用于评价策略价值。

止损变体保持同一策略和配置，只改变行情：

| 场景 | 行情变化 | 止损执行 | 成交价 | 卖出佣金 | Final Cash / Equity | 收益 |
|---|---|---|---:|---:|---:|---:|
| 盘中触及 | 第 6 日 Low=9，Open=13 | 第 6 日触发参考 9.1 | 9.0 | 2.970 | 890.737 | −10.9263% |
| 跳空穿越 | 第 6 日 Open=8、Low=7 | 第 6 日参考 Open=8 | 7.9 | 2.607 | 854.800 | −14.52% |
| 买入当天触及 | 第 5 日 Low=9 | 第 5 日先 BUY 再 Stop SELL | 9.0 | 2.970 | 890.737 | −10.9263% |

三个变体最终持仓全部为 0、无末日待执行单、仅两笔 Trade；没有“满足止损但账户未平仓”。

README 冒烟验证也实际执行：在 PowerShell 设置 `$env:MPLBACKEND='Agg'` 后运行 `python -m examples.ma_cross_backtest`。默认 CSV 全量加载 507 根，成交 31 笔，期末权益 146173.52，总收益 46.17%，年化 20.77%，回撤 −18.01%，Sharpe 0.851。命令成功退出，出现 **1 条** Agg 无法显示 GUI 的 UserWarning；这属于该次无窗口示例运行，pytest 自身为 0 warning。图形内容由既有 `show=False` 自动化测试检查，未人工验证桌面窗口。未新建干净环境执行 `pip install -e ".[dev]"`，不能声称所有安装环境均验证通过。

## 6. 人工计算 vs 框架计算

第 4 日 SMA2=(10+12)/2=11，SMA3=(10+10+12)/3=32/3≈10.666667，产生 BUY。第 3 日 Close=10，因此 TR4=max(13−11, |13−10|, |11−10|)=3；ATR1=3，止损距离为 3×1=3。第 5 日执行价=12+0.1=12.1，固定止损价=12.1−3=9.1。

| 项目 | 独立人工公式 / 值 | 框架核对 |
|---|---|---|
| 风险预算 | 1000×10%=100 | 100 |
| 风险仓位 | floor(100/3)=33 股 | 33 |
| 现金含费上限 | floor(1000/(12.1×1.01))=81 股；取 min(33,81) | 33 股 |
| 买入金额 | 12.1×33=399.3 | 399.3 |
| 买入佣金 | 399.3×1%=3.993 | 3.9930000000000003（浮点表示） |
| 买后现金 | 1000−399.3−3.993=596.707 | 596.707 |
| 含费均价 | (399.3+3.993)/33=12.221 | 12.221 |
| 第 5 日市值 / Equity | 12×33=396；596.707+396=992.707 | 396 / 992.707 |
| 第 5 日未实现损益 | (12−12.221)×33=−7.293 | 由公开 Snapshot 推导并断言一致 |
| 正常卖出价 | 10−0.1=9.9 | 9.9 |
| 卖出金额 / 佣金 | 9.9×33=326.7；326.7×1%=3.267 | 326.7 / 3.267 |
| 正常平仓现金 | 596.707+326.7−3.267=920.14 | 920.14 |
| 完整交易净 PnL | (9.9−12.1)×33−3.993−3.267=−79.86 | Final Cash−Initial Cash=−79.86 |
| 平仓后仓位 / 市值 | 0 / 0 | 0 / 0 |
| Total Return | 920.14/1000−1=−0.07986 | −0.07986000000000004 |
| Maximum Drawdown | 920.14/1025.707−1≈−0.102921204593514 | −0.10292120459351439 |
| 盘中止损净 PnL | (9.0−12.1)×33−3.993−2.970=−109.263 | 890.737−1000=−109.263 |
| 跳空止损净 PnL | (7.9−12.1)×33−3.993−2.607=−145.2 | 854.8−1000=−145.2 |

已实现 PnL 的内部累计公式也逐行检查为 `(SellPrice−含费均价)×Quantity−SellCommission`。测试未跨层读取 `_position`，因此明确区分“通过完整平仓现金损益核对”和“直接读取内部 realized_pnl 字段”；后者没有公共接口，不声称已从结果直接取得。

额外绩效手算序列：Initial=100，Equity=[90,120,96]，收益 −4%，回撤 −20%，年化 `0.96**84−1`；日收益为 −1/10、1/3、−1/5，样本方差 217/2700，Sharpe=`(1/90)/sqrt(217/2700)×sqrt(252)`。正式用例全部核对一致。

## 7. 回测正确性风险

| 检查项 | 判断及证据 | 残余边界 |
|---|---|---|
| Look-ahead Bias | 现有与新用例验证 T Close 信号 → 下一 Bar Open；Order/Trade 都校验执行晚于信号 | 日线时间戳不是精确收盘时间；自定义 Strategy 仍须遵守历史接口约定 |
| 指标数据泄漏 | SMA 单向滚动；TR 仅前收盘；ATR 单向递推；信号前缀/ATR 前缀测试 | Engine 提前加载全部数据用于校验，但交给策略的仅是当前/历史前缀 |
| 成交顺序 | 新优先级测试：跳空止损先于待 SELL；Open 主动 SELL 先于随后 Low 止损；没有双卖 | 日线不能还原盘中路径；Trade 不标明触发原因/订单类型 |
| Cash<0 | 买入含佣金限额、Portfolio 二次保护；超额买入/费用超现金拒绝；浮点 1e−8 内归零 | 金额用 float，非高精度券商结算；非有限扩展模型返回值不全部转换为订单拒绝 |
| Position<0 | Order 正数量；Portfolio 拒绝超额卖出；新失败用例账户不变 | Engine 使用整股；底层领域/Portfolio 仍可接受正的小数数量 |
| 重复下单 | MA 目标变化才发信号；Engine 有仓则忽略 BUY；新连续 BUY 测试只有一次成交 | 止损/买入拒绝后策略 `_last_target` 未与账户同步，目标不变不自动重试/重新入场 |
| 风险预算 | 名义数量按 Equity×RiskFraction/Distance；跳空案例亏损 145.2>预算 100，真实反映穿价和费用 | 风险比例不等于损失硬上限；不包含公司行为、停牌和涨跌停模型 |
| 末日处理 | 末根信号过期，已有持仓按 Close 估值；现有正式测试 | 未自动强平；含持仓的 Final Equity 与 Final Cash 可以不同 |

止损后等待新的均线目标变化属于当前信号驱动策略语义，不是止损未生效。本次明确呈现该限制，不擅自加入自动重入规则。

## 8. 工程质量

目录职责、核心类型注解与必要中文注释基本满足项目约束。Strategy 不读取 CSV/pandas，不修改账户；Broker 与 Portfolio 不互调；Engine 调用公开边界完成定量、成交、入账、止损同步和估值；Analytics 只分析冻结的结果对象。Engine 具有止损编排分支，但未承载 ATR、佣金、现金记账或绩效公式，无需为本次验收大规模重构。

README 提供安装、示例、CSV 格式、测试命令与主要假设；示例实际可运行。构造参数可配置均线、ATR、仓位、费用和滑点；252 个交易日为 Analytics 命名常量，示例默认现金与 MA 参数集中于组装入口。

文档一致性需注意：README “不支持部分卖出”适用于当前 Engine 策略流程；Portfolio 底层本身可以处理部分卖出。README/AGENTS 所说“没有 RiskManager”与实际 `risk/atr_stop.py` 并不矛盾，因为后者不是通用风险管理器。长期指南的 `src/quant`、Paper Trading 和目标风控仅为路线，不是当前交付状态。

本次没有架构/API 改动，不需要迁移；`architecture.md` 与 V0.1 TODO Phase 11 的实现状态已经符合当前代码，不作无关更新。新增验收测试与记录不改变发布能力，因此不额外修改 CHANGELOG 版本条目。

## 9. V1 阻塞问题

**在本次限定的基础回测范围内，没有已复现的阻塞问题。** 56 项正式测试全部通过，正常交易及三种止损闭环的成交价、数量、费用、现金、持仓和总盈亏均与独立手算一致。不存在需要为通过验收立即修复的业务代码范围。

这一结论不是“无任何缺陷”的证明。若使用要求变为真实市场成交、强制风险硬上限、自动止损重入或直接输出分项 PnL，需要另行明确规则并开发，不由本次验收暗中补齐。

## 10. 非阻塞问题

| 问题 | 涉及位置 | 最小后续范围 |
|---|---|---|
| 分项盈亏可观测性不足 | Position / AccountSnapshot / BacktestResult | 如需展示，增加只读已实现/未实现 PnL 字段及含费口径测试 |
| 止损后或拒绝买入后不自动重入 | MACrossStrategy `_last_target`；Engine | 先确定是否等待下一交叉；若要重试，设计明确成交反馈边界，避免策略直接访问账户 |
| 均线相等即空仓，策略参数类型校验不完全提前失败 | MACrossStrategy 构造/目标判断 | 文档明确 `>`/`<=` 规则；对非整数窗口在构造时校验而不是等指标计算报错 |
| 止损记录不含专门触发事件/原 Order | Engine/models，Trade | 如需要交易归因，补充只读原因/订单类型与时间说明；当前成本/现金链无误 |
| 风险策略组合易误配 | Example / RiskBasedPositionSizer | 提供带 ATR 的组装示例；风险仓位器配无距离策略目前会抛明确 ValueError |
| 插件模型与公开对象边界不够严格 | AtrStopPolicy.activate、OrderResult、Position、自定义成本模型 | 增加必要类型/有限值/状态关联校验和测试；内置协作者的常规调用已验证 |
| 自动化覆盖仍有空白 | `tests/` | 可补比例滑点闭环、部分卖出成本、极端/破产指标、错误时间订单等；不把未测当成已测 |
| ruff/mypy 未运行、未验证最低 Python 版本和全新安装 | pyproject / 开发环境 | 按 README 在隔离环境安装 dev 并执行；本次不改变用户环境或依赖 |
| 底层支持部分卖出但 README 描述泛化 | README / Portfolio | 后续小型文字区分 Engine 当前全仓退出与底层能力 |

## 11. 后续高级功能

当前无需实现：实盘/券商 API、实时行情、Tick/Level 2、高频、复杂订单簿、多账户、多资产、并行/分布式/GPU、自动参数优化、Walk Forward、Monte Carlo、机器学习策略、数据库、Web UI 或完整事件总线。

后续按实际学习需求分阶段规划即可。本报告通过的是可加载数据、产生信号、定量成交、计入成本、正确记账、止损平仓并计算基础绩效的有限研究框架。
