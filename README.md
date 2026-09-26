# Quant Forge

Quant Forge 是个人量化交易研究与回测框架。当前 V0.1 支持 CSV 单标的日线、MA Cross、市价单、佣金与滑点、单一多头 Portfolio、回测结果及基础绩效。旧教学 Demo 独立保留在相邻的 `quant-learning` 项目中，不属于本仓库的运行依赖。

## 安装与运行

在项目根目录使用 conda `agent` 环境或其他 Python 3.8+ 环境：

```bash
python -m pip install -e ".[dev]"
python -m examples.ma_cross_backtest
```

默认示例使用 `data/stock_real.csv`，打印交易数、期末权益、总收益、年化收益、最大回撤和 Sharpe。

运行测试：

```bash
python -m pytest
```

## 回测语义

- Strategy 只在完整 Bar 可见后输出目标仓位意图（空仓 `0` 或满仓 `1`）。
- 意图最早在下一根可用 Bar 的 Open 执行。Engine 只在执行 Bar 到达后计算数量，不读取未来价格。
- Broker 负责滑点和佣金，Portfolio 独占现金与持仓状态。
- 每日按 Close 估值。末根 Bar 发出的意图没有后续执行机会，会记录为 `EXPIRED_NO_NEXT_BAR`。
- V0.1 允许小数股，不支持做空、杠杆、多资产或实盘。
- 默认佣金率为 `0.0003`，默认无滑点；可注入固定/百分比佣金和滑点模型。

## 项目结构

```text
src/quant/core/       领域对象和校验
src/quant/data/       DataFeed 与 CSVDataFeed
src/quant/indicators/ 简单移动平均
src/quant/strategy/   Strategy 协议与 MA Cross
src/quant/broker/     市价执行、佣金、滑点
src/quant/portfolio/  现金、持仓、成交入账与估值
src/quant/engine/     回测生命周期与结果模型
src/quant/analytics/  收益、年化、回撤、Sharpe
tests/                单元与集成测试
examples/             端到端运行示例
docs/                 架构基线、迁移任务与长期设计指南
```

## 文档

- [架构设计与长期演进指南](docs/Personal_Quant_Framework_架构设计与长期演进指南.md)
- [当前架构](docs/architecture.md)
- [V0.1 任务与完成记录](docs/V0.1_TODO.md)

量化结果依赖数据、成交时点、费用及指标口径。使用前请阅读架构文档中的时间语义和结果假设。
