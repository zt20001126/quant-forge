# Personal Quant Framework — 架构设计与长期演进指南

> **文档定位**：本项目不是一次性的量化学习 Demo，而是一个由 AI 辅助开发、由开发者持续理解、验证、重构和扩展的个人量化交易框架。
>
> 核心目标不是重新实现 Backtrader，而是建立一个 **结构清晰、职责单一、低耦合、可测试、可扩展、可长期维护** 的量化学习与实验平台。

> **与当前仓库的关系**：本文包含长期目标结构与演进建议，不应覆盖 V0.1 的实际实现事实。当前 QuantForge 包实际位于仓库根目录 `quant/`；V0.1 不含 RiskManager、`config/` 空包或指南中尚未实现的其他模块。代码审查和日常修改以 `docs/architecture.md` 记录的当前实现为准；改变目录结构需单独说明迁移影响。

---

## 1. 项目背景

现有 Demo 已经实现了最小量化回测闭环：

```text
CSV 行情
    ↓
数据校验与排序
    ↓
MA5 / MA20
    ↓
生成交易信号
    ↓
Broker 成交
    ↓
交易记录 / 每日资产曲线
    ↓
收益率 / 最大回撤 / Sharpe
    ↓
图表展示
```

现有 Demo 已具备以下模块：

- CSV 行情加载与校验
- Moving Average 指标
- 双均线策略
- Broker
- Backtest Engine
- Performance Metrics
- Visualization

它非常适合作为新框架的 **V0 原型**，但不建议直接在原有结构上无限增加功能。

原因是随着后续加入：

- 滑点
- 多种手续费模型
- 仓位管理
- 风险管理
- 多股票
- 多策略
- Benchmark
- 参数优化
- Walk Forward
- 事件驱动
- Paper Trading
- 实盘交易

如果缺少稳定的模块边界，很容易逐渐演变成大量模块互相调用、核心逻辑集中在少数文件中的结构。

因此，新框架从 V0.1 开始优先解决的不是“功能数量”，而是 **架构边界**。

---

# 2. 项目核心目标

## 2.1 第一目标：可维护性

代码必须方便未来持续修改，而不是只满足当前 MA 策略。

要求：

- 模块职责清晰
- 依赖方向明确
- 避免循环依赖
- 避免跨层访问内部状态
- 核心业务逻辑可单独测试
- 修改一个模块尽量不影响其他模块
- 新功能优先通过扩展实现

---

## 2.2 第二目标：可阅读性

代码首先服务于“人能理解”。

要求：

- 命名表达业务含义
- 避免过度抽象
- 避免为了设计模式而设计
- 公共接口提供完整类型标注
- 核心逻辑提供必要中文注释
- 复杂逻辑说明“为什么”，而不只是说明“做什么”
- 一个文件尽量只承担一种主要职责

---

## 2.3 第三目标：可扩展性

未来增加新能力时，应尽量满足：

```text
增加功能
    ↓
新增实现 / 扩展接口
    ↓
少量修改现有代码
    ↓
已有模块继续工作
```

而不是：

```text
增加功能
    ↓
修改 Strategy
    ↓
修改 Broker
    ↓
修改 Portfolio
    ↓
修改 Engine
    ↓
旧功能出现回归问题
```

---

## 2.4 第四目标：学习驱动

本项目不是单纯让 AI 自动完成代码。

正确模式：

```text
学习新的量化知识
        ↓
理解它解决什么问题
        ↓
确定它属于框架哪一层
        ↓
设计接口
        ↓
AI 辅助实现
        ↓
阅读代码
        ↓
测试与验证
        ↓
纳入框架
```

必须能够解释核心模块的工作方式。

---

# 3. 架构设计原则

## 3.1 单一职责原则

每个模块只解决自己的问题。

### Strategy

负责：

```text
行情 / 指标
    ↓
策略判断
    ↓
交易意图
```

不负责：

- 扣现金
- 修改持仓
- 计算手续费
- 模拟成交
- 计算最终收益

---

### Broker

负责：

```text
Order
  ↓
成交规则
  ↓
Trade
```

包括：

- 市价单处理
- 成交价格
- 手续费
- 滑点
- 后续订单类型

Broker 不负责策略判断。

---

### Portfolio

负责：

```text
Cash
Position
Trade
   ↓
账户状态
   ↓
Portfolio Value
```

包括：

- 现金
- 持仓
- 成交后的账户更新
- 资产估值

---

### RiskManager

负责：

```text
OrderIntent
     ↓
风险检查
     ↓
允许 / 拒绝 / 调整
```

未来可以加入：

- 最大仓位
- 单笔风险
- 最大回撤限制
- 最大持仓数量
- 单资产暴露限制

---

### BacktestEngine

只负责调度。

例如：

```text
获取下一根 Bar
      ↓
Strategy.on_bar()
      ↓
OrderIntent
      ↓
RiskManager
      ↓
Order
      ↓
Broker
      ↓
Trade
      ↓
Portfolio
      ↓
记录 Equity
```

Engine 不应该自己实现 MA、手续费、仓位计算等具体业务。

---

### Analytics

只负责分析已经产生的结果：

- Total Return
- Annual Return
- Max Drawdown
- Sharpe Ratio
- Win Rate
- Profit Factor
- Benchmark Comparison

它不参与交易决策。

---

# 4. 推荐项目结构

```text
quant-framework/
│
├── src/
│   └── quant/
│       │
│       ├── core/
│       │   ├── enums.py
│       │   ├── event.py
│       │   ├── bar.py
│       │   ├── order.py
│       │   ├── trade.py
│       │   └── position.py
│       │
│       ├── data/
│       │   ├── base.py
│       │   ├── models.py
│       │   └── csv_feed.py
│       │
│       ├── indicators/
│       │   ├── base.py
│       │   └── moving_average.py
│       │
│       ├── strategy/
│       │   ├── base.py
│       │   └── ma_cross.py
│       │
│       ├── broker/
│       │   ├── base.py
│       │   ├── broker.py
│       │   ├── commission.py
│       │   └── slippage.py
│       │
│       ├── portfolio/
│       │   ├── portfolio.py
│       │   └── position_manager.py
│       │
│       ├── risk/
│       │   ├── base.py
│       │   └── risk_manager.py
│       │
│       ├── engine/
│       │   └── backtest_engine.py
│       │
│       ├── analytics/
│       │   ├── metrics.py
│       │   └── report.py
│       │
│       └── config/
│           └── settings.py
│
├── tests/
│   ├── unit/
│   │   ├── test_strategy.py
│   │   ├── test_broker.py
│   │   ├── test_portfolio.py
│   │   └── test_metrics.py
│   │
│   └── integration/
│       └── test_backtest.py
│
├── examples/
│   └── ma_cross_backtest.py
│
├── data/
│
├── docs/
│   ├── architecture.md
│   ├── coding_standard.md
│   ├── testing_standard.md
│   └── development_workflow.md
│
├── AGENTS.md
├── pyproject.toml
├── README.md
└── .gitignore
```

> 注意：这是目标结构，不要求 V0.1 一次实现所有文件。没有实际职责的模块不要为了“架构完整”提前创建大量空壳。

---

# 5. 分层与依赖方向

这是整个项目最重要的约束之一。

推荐逻辑：

```text
                 Application / Examples
                         │
                         ↓
                       Engine
                  ┌──────┼──────┐
                  ↓      ↓      ↓
              Strategy Broker  Risk
                  │      │      │
                  └──────┼──────┘
                         ↓
                     Portfolio

Data ─────→ Core ←──── 各领域模块

Analytics ←──── Backtest Result
```

核心原则：

> **高层业务逻辑不依赖具体基础设施实现。**

---

## 5.1 Strategy 不应该知道数据来自哪里

错误：

```python
class MACrossStrategy:
    def __init__(self):
        self.data = CSVDataLoader("data.csv")
```

Strategy 因此和 CSV 强耦合。

以后切换：

- 数据库
- AkShare
- Tushare
- API
- WebSocket
- 实时行情

就需要修改 Strategy。

正确思路：

```python
def on_bar(self, bar: Bar) -> list[OrderIntent]:
    ...
```

Strategy 只认识领域对象：

- Bar
- Indicator
- OrderIntent

它不关心数据来源。

---

## 5.2 Strategy 不直接修改 Portfolio

错误：

```python
if signal == 1:
    portfolio.cash -= amount
    portfolio.position += quantity
```

这会导致 Strategy 与 Portfolio、成交逻辑严重耦合。

正确：

```text
Strategy
   ↓
OrderIntent
   ↓
RiskManager
   ↓
Broker
   ↓
Trade
   ↓
Portfolio
```

---

# 6. 核心领域对象

V0.1 建议至少明确以下概念。

## 6.1 Bar

表示一根行情 K 线：

```python
@dataclass(frozen=True)
class Bar:
    symbol: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
```

---

## 6.2 OrderIntent

表示策略产生的“交易意图”。

例如：

```text
BUY AAPL
```

它不是最终成交。

这样 Strategy 不需要知道：

- 是否有足够资金
- 实际成交价格
- 手续费
- 滑点

---

## 6.3 Order

表示经过系统确认、准备交给 Broker 的订单。

未来可以扩展：

```text
Market Order
Limit Order
Stop Order
```

---

## 6.4 Trade

表示真实模拟成交结果。

建议包含：

```text
trade_id
order_id
symbol
side
price
quantity
commission
timestamp
```

---

## 6.5 Position

表示某资产当前持仓状态。

未来可以包含：

```text
symbol
quantity
average_price
market_value
unrealized_pnl
realized_pnl
```

---

# 7. 核心接口设计

第一版就应该建立接口边界，但不要过度设计。

## 7.1 Strategy

```python
from abc import ABC, abstractmethod


class Strategy(ABC):

    @abstractmethod
    def on_bar(self, bar: Bar) -> list[OrderIntent]:
        """处理新行情并返回交易意图。"""
        raise NotImplementedError
```

以后增加：

```text
MACrossStrategy
RSIStrategy
MomentumStrategy
MeanReversionStrategy
```

无需修改 Engine。

---

## 7.2 DataFeed

```python
class DataFeed(ABC):

    @abstractmethod
    def __iter__(self):
        """按时间顺序产生行情。"""
        raise NotImplementedError
```

实现：

```text
CSVDataFeed
```

未来：

```text
DatabaseDataFeed
APIDataFeed
LiveDataFeed
```

---

## 7.3 CommissionModel

```python
class CommissionModel(ABC):

    @abstractmethod
    def calculate(self, price: float, quantity: float) -> float:
        raise NotImplementedError
```

可以扩展：

```text
NoCommission
PercentageCommission
FixedCommission
```

---

## 7.4 SlippageModel

```python
class SlippageModel(ABC):

    @abstractmethod
    def apply(self, price: float, side: Side) -> float:
        raise NotImplementedError
```

未来：

```text
NoSlippage
FixedSlippage
PercentageSlippage
```

---

## 7.5 RiskManager

```python
class RiskManager(ABC):

    @abstractmethod
    def evaluate(
        self,
        intent: OrderIntent,
        portfolio: Portfolio,
    ) -> RiskDecision:
        raise NotImplementedError
```

V0.1 可以只有简单实现，但保留扩展边界。

---

# 8. 一次回测的标准执行流程

建议统一定义回测生命周期。

```text
BacktestEngine.run()
        │
        ↓
DataFeed.next()
        │
        ↓
       Bar
        │
        ↓
Strategy.on_bar()
        │
        ↓
   OrderIntent
        │
        ↓
RiskManager.evaluate()
        │
        ↓
      Order
        │
        ↓
Broker.execute()
        │
        ├── SlippageModel
        │
        └── CommissionModel
        ↓
      Trade
        │
        ↓
Portfolio.apply_trade()
        │
        ↓
Portfolio.mark_to_market()
        │
        ↓
记录 Equity Snapshot
        │
        ↓
下一根 Bar
```

结束后：

```text
BacktestResult
      ↓
Analytics
      ↓
PerformanceReport
```

---

# 9. 必须解决的前视偏差问题

现有教学 Demo 使用：

```text
当天 Close
    ↓
计算 MA
    ↓
产生 Signal
    ↓
仍然按照当天 Close 成交
```

这个模型存在前视偏差。

因为：

> 只有当天交易结束后，才能确定当天完整的 Close。

如果利用这个 Close 产生信号，又假设自己能够按照同一个 Close 成交，相当于使用了当时不可完整获得的信息。

因此新框架应该明确时间语义。

最简单的 V0.1 规则可以是：

```text
T 日收盘
   ↓
Strategy 根据 T 日及历史数据产生信号
   ↓
生成 Order
   ↓
T+1 日 Open 成交
```

即：

```text
Signal Time != Execution Time
```

这是新框架相比旧 Demo 必须优先改进的地方之一。

---

# 10. V0.1 功能范围

第一版必须克制。

目标不是实现大量功能，而是验证架构。

## 行情

仅支持：

```text
CSV
日线
单股票
OHLCV
```

## Strategy

仅：

```text
MA Cross
```

## Order

仅：

```text
Market Order
```

## Portfolio

仅：

```text
Cash
Single Position
Portfolio Value
```

## Broker

支持：

```text
Market Execution
Commission
Slippage
```

## Risk

V0.1 可以非常简单：

```text
禁止资金不足
禁止负持仓
禁止非法数量
```

## Analytics

支持：

```text
Total Return
Annualized Return
Max Drawdown
Sharpe Ratio
```

## 输出

至少提供：

```text
Trade Records
Daily Equity Curve
Performance Summary
```

---

# 11. V0.1 明确不做什么

暂时不要实现：

- 高频交易
- Tick 数据
- Level 2
- 多账户
- 分布式回测
- GPU 回测
- 复杂订单簿
- 期权
- 期货保证金
- 做空
- 杠杆
- 实盘交易
- Web 管理后台
- 数据库
- 微服务

原因：

> 当前阶段最重要的是验证架构和理解回测系统，而不是功能数量。

---

# 12. 开发规范

建议将以下规则同时写入 `AGENTS.md`。

## 12.1 基本原则

1. 优先最小修改。
2. 禁止无关重构。
3. 禁止跨层直接操作内部状态。
4. 禁止循环依赖。
5. Core 不依赖具体基础设施。
6. 新功能优先通过扩展实现。
7. 公共函数必须包含类型标注。
8. 核心逻辑必须有必要的中文注释。
9. 一个模块只承担明确职责。
10. 新功能必须增加对应测试。
11. 修改核心接口必须说明原因和影响范围。
12. 不允许为了“未来可能需要”进行大量提前抽象。

---

# 13. AI 开发规范

AI 是实现助手，不是架构决策的唯一来源。

每次修改代码之前，要求 AI 先输出：

```text
1. 需求理解
2. 当前实现分析
3. 影响范围
4. 计划修改文件
5. 实现方案
6. 是否影响已有接口
7. 潜在风险
8. 测试方案
```

确认方案后再修改。

---

## 13.1 推荐 AI 提示词模板

```text
你正在维护一个长期演进的个人量化交易框架。

本项目优先级：

可维护性 > 正确性边界清晰 > 可扩展性 > 功能数量。

开发要求：

1. 修改前先阅读 AGENTS.md 和 docs/architecture.md。
2. 先分析现有代码，不要直接修改。
3. 优先最小修改。
4. 禁止无关重构。
5. 禁止破坏现有分层。
6. Strategy 不直接操作 Portfolio。
7. Strategy 不依赖具体数据源。
8. Broker 负责成交相关逻辑。
9. Portfolio 负责账户与持仓状态。
10. Engine 只负责编排，不承载具体策略/指标逻辑。
11. 新增功能必须增加测试。
12. 公共接口必须有类型标注。
13. 核心业务逻辑使用必要的中文注释。
14. 修改完成后运行全部测试。
15. 输出自测报告。

开始编码之前先输出：

- 需求理解
- 当前实现
- 影响范围
- 修改文件
- 实现方案
- 潜在风险
- 测试方案

不要直接开始编码。
```

---

# 14. 测试规范

量化框架尤其需要测试，因为：

> “程序能够运行”不代表“回测逻辑正确”。

---

## 14.1 Unit Test

每个核心模块单独测试。

例如 Broker：

```text
给定：

Cash = 100000
Price = 100
Commission = 0.03%

执行 BUY

验证：

成交数量正确
Commission 正确
Cash 不为负
Trade 内容正确
```

---

## 14.2 Portfolio Test

验证：

```text
Cash + Position Market Value
=
Portfolio Value
```

并测试：

- 买入
- 卖出
- 空仓
- 全仓
- 连续行情变化

---

## 14.3 Strategy Test

构造极小行情：

```text
Day 1  MA5 < MA20
Day 2  MA5 > MA20
```

验证是否只产生预期信号。

---

## 14.4 Integration Test

完整执行：

```text
CSV
 ↓
DataFeed
 ↓
Strategy
 ↓
Engine
 ↓
Broker
 ↓
Portfolio
 ↓
Analytics
```

检查最终结果。

---

## 14.5 Regression Test

每次新增功能后必须保证旧测试继续通过。

例如加入 Slippage：

```text
pytest
```

不能只测试 Slippage 自己。

---

# 15. 数据正确性原则

行情进入系统时至少检查：

```text
date
open
high
low
close
volume
```

并检查：

- 日期可解析
- 时间升序
- 必需字段无空值
- OHLC 数据合法
- 重复时间处理策略明确
- 数据长度满足指标计算要求

后续还需要逐渐学习并处理：

- 前复权 / 后复权
- 股票拆分
- 分红
- 停牌
- 退市
- Survivorship Bias
- Look-ahead Bias
- 数据缺失

---

# 16. 配置与代码分离

不要把参数散落在代码中。

例如：

```python
INITIAL_CASH = 100_000
COMMISSION_RATE = 0.0003
SHORT_WINDOW = 5
LONG_WINDOW = 20
```

应逐渐集中到配置对象：

```python
@dataclass
class BacktestConfig:
    initial_cash: float
    commission_rate: float
    short_window: int
    long_window: int
```

未来可以继续演进为配置文件，但 V0.1 不必急着引入复杂配置系统。

---

# 17. 日志规范

框架运行过程建议逐步引入统一日志。

例如：

```text
INFO  Backtest started
INFO  Data loaded: 1000 bars
INFO  BUY AAPL quantity=100 price=10.23
INFO  SELL AAPL quantity=100 price=11.02
INFO  Backtest completed
```

不要大量使用：

```python
print(...)
```

正式模块优先使用：

```python
logging
```

示例脚本可以负责最终的人类可读输出。

---

# 18. 异常处理

建议逐渐建立自己的异常体系：

```text
QuantError
├── DataError
├── OrderError
├── BrokerError
├── PortfolioError
└── ConfigurationError
```

避免所有地方直接：

```python
raise Exception(...)
```

错误信息应该能够告诉开发者：

```text
发生了什么
为什么发生
哪个参数有问题
```

---

# 19. 代码质量工具

建议逐步加入：

```text
pytest
ruff
mypy
```

职责：

```text
pytest
→ 测试

ruff
→ 格式 / lint

mypy
→ 类型检查
```

后续可以加入：

```text
pre-commit
coverage
```

但不要在 V0.1 一次引入过多工程工具。

---

# 20. Git 开发规范

推荐小步提交。

例如：

```text
feat: add Bar domain model

feat: add CSV data feed

feat: add strategy interface

feat: implement MA cross strategy

feat: add commission model

feat: add backtest engine

test: add broker unit tests

refactor: decouple strategy from portfolio
```

不要积累大量功能之后一次提交。

---

# 21. 文档规范

至少长期维护：

```text
README.md
docs/architecture.md
docs/development_workflow.md
docs/testing_standard.md
AGENTS.md
```

其中：

### README

回答：

```text
这个项目是什么？
怎么安装？
怎么运行？
```

### architecture.md

回答：

```text
为什么这样设计？
模块之间怎么交互？
依赖方向是什么？
```

### development_workflow.md

回答：

```text
新增功能应该按照什么流程？
```

### testing_standard.md

回答：

```text
什么功能必须测试？
如何验证回测正确性？
```

### AGENTS.md

回答：

```text
AI 修改这个项目必须遵守什么规则？
```

---

# 22. 推荐开发流程

以后每学习一个新功能，都遵循：

```text
学习概念
   ↓
确认业务意义
   ↓
确定所属模块
   ↓
写需求
   ↓
分析影响范围
   ↓
设计接口
   ↓
写测试 / 测试案例
   ↓
AI 辅助实现
   ↓
Code Review
   ↓
运行测试
   ↓
人工验证
   ↓
更新文档
   ↓
Git Commit
```

---

# 23. 版本演进路线

## V0.1 — 基础框架

目标：

> 建立稳定架构。

包含：

- CSV
- 单股票
- 日线
- MA Cross
- Market Order
- Commission
- Slippage 基础接口
- Portfolio
- Backtest Engine
- Total Return
- Annualized Return
- Max Drawdown
- Sharpe
- Unit Tests
- 可选的静态回测结果图（价格涨跌、成交位置与权益曲线）

---

## V0.2 — 仓位管理

学习：

- Fixed Position Size
- Percentage Position Size
- Position Sizing

新增：

```text
PositionSizer
```

---

## V0.3 — 风险管理

学习：

- Stop Loss
- Take Profit
- Maximum Position
- Risk Per Trade

增强：

```text
RiskManager
```

---

## V0.4 — 多资产

从：

```text
Single Symbol
```

升级：

```text
Multiple Symbols
```

重点处理：

- 多 Position
- 资金分配
- 时间对齐
- 缺失行情

---

## V0.5 — Benchmark

加入：

```text
Strategy Return
      VS
Benchmark Return
```

例如 Buy & Hold。

---

## V0.6 — 多策略

允许：

```text
Strategy A
Strategy B
Strategy C
```

使用同一套：

```text
Data
Broker
Portfolio
Analytics
```

---

## V0.7 — 参数优化

例如：

```text
MA(5, 20)
MA(10, 30)
MA(20, 60)
```

但需要开始警惕：

```text
Overfitting
```

---

## V0.8 — Walk Forward

学习：

```text
Training Period
      ↓
Parameter Selection
      ↓
Out-of-Sample
      ↓
Rolling Forward
```

---

## V0.9 — Event Driven

逐渐形成：

```text
MarketEvent
SignalEvent
OrderEvent
FillEvent
```

此阶段再决定是否需要完整事件总线。

不要在 V0.1 为了“高级”而强行事件化。

---

## V1.0 — Paper Trading

当回测框架足够稳定后，再考虑：

```text
Live Data
    ↓
Strategy
    ↓
Risk
    ↓
Paper Broker
    ↓
Portfolio
```

最终才能进一步考虑真实 Broker Adapter。

---

# 24. 新知识如何映射到框架

以后每学一个量化概念，都问两个问题：

> **问题 1：它解决量化交易中的什么问题？**

> **问题 2：它应该属于框架中的哪一层？**

例如：

| 学习内容 | 框架位置 |
|---|---|
| MA / RSI / MACD / ATR | indicators |
| 均线策略 | strategy |
| 止盈止损 | strategy / risk（取决于定义） |
| 仓位管理 | portfolio / position sizing |
| 手续费 | broker / commission |
| 滑点 | broker / slippage |
| 最大回撤 | analytics |
| Sharpe | analytics |
| CSV | data |
| 实时行情 | data |
| 市价单 | broker |
| 限价单 | broker |
| 风控 | risk |
| Walk Forward | optimization / research |
| 实盘 API | broker adapter / infrastructure |

这张映射表应该随着学习不断更新。

---

# 25. 从现有 Demo 迁移到 V0.1

不建议直接删除现有 Demo。

推荐：

```text
旧 Demo
   ↓
作为行为参考 / 验证基准
   ↓
建立新的 src/quant
   ↓
逐模块迁移
   ↓
测试新旧结果
   ↓
新架构稳定
   ↓
旧 Demo 进入 archive 或 examples
```

推荐迁移顺序：

```text
Step 1
建立项目骨架

Step 2
定义 Bar / OrderIntent / Order / Trade

Step 3
迁移 DataLoader → CSVDataFeed

Step 4
迁移 Moving Average

Step 5
定义 Strategy Interface

Step 6
迁移 MA Strategy

Step 7
拆分 Broker / Commission / Slippage

Step 8
建立 Portfolio

Step 9
重写 BacktestEngine

Step 10
迁移 Performance Metrics

Step 11
建立 Unit Tests

Step 12
建立 Integration Test

Step 13
比较新旧 Demo 结果

Step 14
修复旧 Demo 中的同日 Close 信号与成交问题

Step 15
更新 README / Architecture
```

---

# 26. 架构 Review Checklist

每次开发新功能前后检查：

## Architecture

- [ ] 这个功能属于哪一层？
- [ ] 是否跨层直接访问内部状态？
- [ ] 是否产生循环依赖？
- [ ] 是否可以通过接口扩展？
- [ ] 是否真的需要新增抽象？

## Code

- [ ] 命名是否清晰？
- [ ] 函数是否职责单一？
- [ ] 是否存在超长函数？
- [ ] 是否有重复逻辑？
- [ ] 公共接口是否有类型标注？
- [ ] 核心复杂逻辑是否有必要注释？

## Quant Correctness

- [ ] 是否存在未来函数？
- [ ] Signal 和 Execution 时间是否合理？
- [ ] 手续费是否正确？
- [ ] 滑点是否正确？
- [ ] Portfolio Value 是否正确？
- [ ] 是否错误使用未来数据？

## Tests

- [ ] 新功能是否有 Unit Test？
- [ ] 是否需要 Integration Test？
- [ ] 旧测试是否全部通过？
- [ ] 是否覆盖边界情况？

## Documentation

- [ ] README 是否需要更新？
- [ ] architecture.md 是否需要更新？
- [ ] 新模块职责是否已经记录？
- [ ] 是否记录重要设计决策？

---

# 27. 架构决策原则

未来遇到设计选择时，按照以下优先级：

```text
正确性
  >
可理解性
  >
可维护性
  >
可测试性
  >
可扩展性
  >
性能
  >
代码炫技
```

对于当前学习阶段：

> 不要为了理论上的高性能牺牲可读性。

只有真正遇到性能瓶颈以后再优化。

---

# 28. AI 与开发者的职责边界

## AI 负责

- 生成样板代码
- 实现明确接口
- 编写测试
- 查找重复代码
- 辅助重构
- 生成文档
- Code Review
- 分析 Bug
- 提供设计候选方案

## 开发者负责

- 理解业务
- 确定架构
- 判断量化逻辑是否正确
- 判断时间语义是否正确
- 判断回测假设是否合理
- 验证 AI 代码
- 决定是否接受重构
- 控制项目演进方向

核心原则：

> **AI 可以写代码，但开发者必须拥有框架。**

所谓“拥有”，不是代码存在自己电脑里，而是：

> 你能够解释这个系统为什么这样设计，以及一笔交易从行情进入系统到最终进入绩效统计经历了什么。

---

# 29. 项目的长期目标

最终希望形成：

```text
                     Quant Framework
                           │
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
        Data            Strategy           Risk
          │                │                │
          └────────────────┼────────────────┘
                           ↓
                         Engine
                           ↓
                         Broker
                           ↓
                       Portfolio
                           ↓
                       Analytics
```

它应该同时具备三个属性：

### 学习平台

每学一个量化知识，可以在框架中找到对应位置。

### 实验平台

可以快速实现和验证不同策略。

### 工程项目

代码结构、测试、文档、Git 历史都能够长期维护。

---

# 30. 当前阶段最重要的事情

现在不要继续堆大量策略。

第一阶段目标应该是：

> **把现有 Mini Quant Demo 重构成结构稳定的 Quant Framework V0.1。**

重点不是：

```text
支持多少策略？
```

而是：

```text
模块边界是否清晰？
依赖方向是否合理？
测试是否可靠？
回测时间语义是否正确？
以后新增功能是否容易？
AI 是否能够按照统一规范继续维护？
```

当 V0.1 稳定以后，再把每一个新的量化知识点变成一次框架升级。

---

# 31. V0.1 完成定义（Definition of Done）

只有同时满足以下条件，V0.1 才算完成：

- [ ] 项目采用清晰的 `src/quant` 分层结构
- [ ] Data / Strategy / Broker / Portfolio / Engine / Analytics 职责清晰
- [ ] Strategy 不依赖 CSV 等具体数据源
- [ ] Strategy 不直接修改 Portfolio
- [ ] Commission 和 Slippage 具备独立边界
- [ ] Signal Time 与 Execution Time 明确区分
- [ ] 不再使用“当天 Close 产生信号并按当天 Close 成交”的教学假设
- [ ] MA Cross 可以完整运行
- [ ] 可以输出交易记录
- [ ] 可以输出每日 Equity Curve
- [ ] 可以计算基础绩效指标
- [ ] 核心模块存在 Unit Test
- [ ] 完整流程存在 Integration Test
- [ ] 全部测试通过
- [ ] README 可以让新开发者运行项目
- [ ] architecture.md 可以解释模块职责和依赖
- [ ] AGENTS.md 可以约束后续 AI 开发行为

完成这些以后：

```text
Quant Framework V0.1
```

才真正成为后续学习和持续演进的基础。

---

## 最终原则

这个项目长期坚持：

> **先理解，再抽象；先正确，再优化；先稳定边界，再增加功能。**

以及：

> **每学习一个新的量化知识，就让框架获得一项新的、经过测试和文档化的能力。**
