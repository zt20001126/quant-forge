# Changelog

All notable changes to QuantForge will be documented in this file.

## [Unreleased]

### Added
- Buy & Hold 理论价格基准、同资金/标的/完整区间的四项绩效对比及可选双权益曲线；新增 `run_benchmark_example`，保留原有回测接口。基准采用首日 Open、小数股、零成本口径。
- 增加公开边界与止损生命周期回归测试，以及 Python 3.10 的 pytest/ruff/mypy CI 检查配置。
- 示例集中参数 `ExampleConfig`、可选图表标题和标准 logging 回测诊断。
- 可选 ATR 固定保护止损与基于止损距离的风险比例整股定仓，止损触发经 Broker 成本模型及 Portfolio 入账。
- 独立 True Range 与 Wilder ATR 指标计算，支持周期配置和明确的暖机期结果。
- MA Cross 示例的静态回测图：收盘价涨跌、实际买卖成交点与组合权益曲线。
- `docs/changes/` 变更记录机制及任务记录模板。
- 固定比例仓位管理 `FixedFractionPositionSizer`，支持整股向下取整和比例配置。

### Changed
- Analytics 提供共用权益绩效入口，原有 `calculate_performance` 保留并复用相同公式；对比示例只读取一次行情。
- 项目 Python 支持范围收紧为 3.10.x，Ruff 和 mypy 目标版本统一到 Python 3.10。
- 仓位器比例为只读配置；Broker 报价参数、止损激活和订单结果一致性校验更严格，订单拒绝记录具体原因。
- MA 策略仅计算所需 SMA 窗口，目标不变时不重算 ATR；mypy 覆盖业务代码、示例和测试并要求完整函数注解。

### Fixed
- 修复合法零 ATR 行情导致保护入场异常、跳空止损后同日新仓跳过保护，以及容差超卖产生额外现金的问题。
- 保留小数股剩余持仓；拒绝非有限费用/报价，阻止非法或溢出成交部分更新账户，并明确绩效溢出错误。
- 修复固定比例仓位在浮点边界下少买整股，以及卖出后容差内负现金导致绩效拒绝的问题。

### Removed

## [0.1.0] - 2026-09-26

### Added
- QuantForge V0.1 单标的日线回测框架。
- CSVDataFeed 行情读取、OHLCV 校验、时间排序与重复日期检查。
- 简单移动平均和 MA Cross 目标仓位策略。
- 市价订单模拟、佣金与滑点模型。
- 单标的多头 Portfolio、成交入账和每日估值。
- BacktestEngine 与交易记录、订单结果、未执行订单及权益曲线。
- 总收益、年化收益、最大回撤和 Sharpe 基础绩效指标。
- Core、Data、Indicator、Strategy、Broker、Portfolio、Engine、Analytics 单元测试及 CSV 到结果的集成测试。
- 项目架构文档、V0.1 开发任务记录和 AI 开发约束。

### Changed

### Fixed

### Removed
