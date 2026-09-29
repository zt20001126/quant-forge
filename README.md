# QuantForge

A maintainable quantitative trading framework for learning, research, and backtesting.

QuantForge 是独立的个人量化研究与回测项目。当前版本为 **V0.1**，重点是清晰的模块边界、可验证的回测时间语义和可维护的 Python 实现，不提供实盘交易能力。相邻的 `quant-learning` 是历史教学 Demo，不是本项目的运行依赖。

## V0.1 当前能力

- CSV 单标的日线 OHLCV 读取、校验与时间排序。
- 简单移动平均、True Range、Wilder ATR 指标计算和 MA Cross 空仓/满仓目标仓位策略。
- 可选 MA Cross ATR 止损距离、风险比例定仓和 ATR 固定保护止损。
- 市价单模拟、比例/固定佣金、无/固定/比例滑点。
- 单标的多头 Portfolio，支持固定比例/风险比例整股仓位计算、成交入账及每日估值。
- 回测交易记录、订单结果、未执行订单、Equity 曲线。
- 总收益、年化收益、最大回撤和 Sharpe Ratio。
- 示例运行后显示收盘价涨跌、买卖成交点和组合权益曲线。

V0.1 不含 RiskManager 模块；非法数量、资金不足、禁止负持仓等边界由现有领域校验、Broker 和 Portfolio 处理。

## 架构与数据流

```text
CSVDataFeed → Bar → Strategy → OrderIntent → BacktestEngine
                                      ↓             ↓
                               下根 Bar 的 Open ← Order
                                                    ↓
                                      Broker → Trade
                                                    ↓
                                    Portfolio → EquitySnapshot
                                                    ↓
                                        BacktestResult → Analytics
```

`quant/core` 保存领域对象；`data` 负责行情读取和校验；`indicators` 计算指标；`strategy` 产生意图；`risk` 持有 ATR 保护止损规则；`broker` 执行订单并计算交易成本；`portfolio` 独占账户状态；`engine` 编排生命周期；`analytics` 只消费结果。未建立通用 RiskManager 或空配置模块。

`true_range(bars)` 与 `average_true_range(bars, period)` 使用 Wilder 算法计算 TR/ATR。配置 MA Cross 的 `atr_period` 和 `atr_multiplier` 后，买入意图会附带 `ATR × multiplier` 止损距离；ATR 未就绪时策略延迟买入信号。

## 仓位管理 / Position Sizing

仓位管理根据账户权益、配置比例/风险和执行价格，把策略的买入意图换算成可提交的买入股数。Strategy 只表达 BUY/SELL（当前通过目标仓位 `1`/`0` 表达），不决定买入数量。支持固定比例与风险比例两种仓位器。

```text
Quantity = floor((Equity × PositionRatio) / Price)
```

例如权益为 `100000`、比例为 `0.2`、执行报价为 `50`，可投入金额为 `20000`，数量为 `400` 股。Engine 在下一根 Bar 的 Open 到达后，使用该 Open 对账户估值并结合 Broker 滑点报价计算数量；佣金预算、可用现金进一步限制买入数量。若权益或价格无效、资金不足以买入一股，数量为零且不会生成有效买单。卖出订单按当前持仓全部卖出，不通过买入仓位器重新计算。

比例通过 Engine 组装时注入，不写入策略：

```python
from quant.engine.backtest_engine import BacktestEngine
from quant.portfolio.position_sizer import FixedFractionPositionSizer

engine = BacktestEngine(
    data_feed, strategy, broker, portfolio,
    position_sizer=FixedFractionPositionSizer(position_ratio=0.2),
)
```

`position_ratio` 与 `risk_fraction` 必须满足 `(0, 1]`。风险定仓公式为 `floor(Equity × RiskFraction / StopDistance)`，例如权益 `10000`、风险比例 `1%`、止损距离 `4` 时买入 `25` 股。最终数量还受现金、滑点报价和佣金约束。买入成交后，固定止损价为实际买入价减去止损距离；日线跳空时按 Open 作为参考价，盘中 Low 触及时按止损价作为参考价，再应用卖出滑点和佣金。跳空、滑点、费用可能令实际损失超过风险预算；止损不追踪。

## 项目结构

```text
quant/                  可安装的 Python 包
  core/                 Bar、Order、Trade、Position 和校验
  data/                 DataFeed 协议和 CSV 适配
  indicators/           SMA、True Range、Wilder ATR
  risk/                 ATR 保护止损状态及触发规则
  strategy/             策略协议和 MA Cross
  broker/               市价执行、佣金和滑点
  portfolio/            现金、持仓、仓位计算、成交入账和估值
  engine/               回测编排、结果与权益快照
  analytics/            绩效指标
tests/unit/             单元测试
tests/integration/      CSV 到结果的集成测试
examples/               MA Cross 可运行示例
data/                   示例行情 CSV
docs/                   架构基线、长期指南和 V0.1 TODO
```

## 环境与安装

- Python 3.8 或更高版本
- 开发依赖：pytest、ruff、mypy

在仓库根目录安装：

```bash
python -m pip install -e ".[dev]"
```

## 快速开始

```bash
python -m examples.ma_cross_backtest
```

示例默认读取 `data/stock_real.csv`，输出交易数、期末权益及绩效指标，随后弹出回测图表窗口。图中上半部分显示收盘价、逐日涨跌和买卖成交，下半部分显示组合权益。关闭图表窗口后程序退出。也可以在 Python 中传入自己的 CSV：

```python
from examples.ma_cross_backtest import run_example
from quant.data.csv_feed import CSVDataFeed
from quant.visualization import plot_backtest

csv_path = "path/to/bars.csv"
result, metrics = run_example(csv_path, symbol="DEMO")
plot_backtest(list(CSVDataFeed(csv_path, "DEMO")), result)
print(len(result.trades), metrics.total_return)
```

CSV 必须包含 `date,open,high,low,close,volume` 列。文件读入后会按时间排序；空数据、重复时间、非法数值及无效 OHLCV 会报错。

## 检查与测试

```bash
python -m pytest
ruff check .
mypy quant
```

## 回测假设

- **Signal Time / Execution Time**：策略在 T 日完整 Bar 可见后产生信号；订单最早于下一根可用 Bar（通常 T+1）的 Open 执行。不会用 T 日 Close 产生信号后又假设按该 Close 成交。
- **定量时点**：Engine 等执行 Bar 到达后，按该 Bar 的 Open 估值权益，并用滑点报价、仓位器、佣金和可用现金确定整股买入数量；风险定仓要求买入意图包含止损距离。
- **ATR 止损**：在保护性买入成交入账后固定止损价；跳空按 Open、盘中触及按止损价确定 Broker 参考价，再应用滑点和佣金。
- **成交成本**：Broker 按方向应用滑点，并在最终 Trade 上记录一次佣金。可买数量计算中的佣金调用用于报价，不会重复入账。
- **账户与估值**：Portfolio 根据成交 Trade 更新现金与持仓；每根 Bar 的交易处理后按 Close 估值。权益等于现金加持仓市值。
- **末根信号**：没有下一根 Bar 可执行的意图记为 `EXPIRED_NO_NEXT_BAR`；该未执行信号不改变账户。
- **绩效口径**：收益和回撤以初始资金为基准；年化按 252 个交易日；Sharpe 默认年化无风险利率为 0。

## 当前限制

仅支持单标的日线 CSV、MA Cross、开仓市价单和 ATR 固定保护止损、多头单持仓与整股仓位；不支持部分卖出、做空、杠杆、多资产、复权/公司行为处理、通用 RiskManager、追踪止损、参数优化、Walk Forward、事件驱动、数据库、Web UI 或实盘交易。真实研究结果受数据质量、费用假设和成交模型影响。

## Roadmap

V0.2 及以后能力按 [V0.1 TODO 与演进记录](docs/V0.1_TODO.md) 和长期架构指南规划，均为 **Planned**，不属于当前支持范围。

## 开发规范与文档

开始修改前阅读 [AGENTS.md](AGENTS.md) 与 [当前架构](docs/architecture.md)。更完整的设计依据见[长期架构指南](docs/Personal_Quant_Framework_架构设计与长期演进指南.md)。文档中的实现状态以代码和测试为准。

版本级变化见 [CHANGELOG.md](CHANGELOG.md)；重要开发任务的背景与验证记录见 [docs/changes/README.md](docs/changes/README.md)。

## Disclaimer

QuantForge 是学习和研究用的回测框架，不构成投资建议。模拟回测不能保证未来表现或真实市场成交结果。
