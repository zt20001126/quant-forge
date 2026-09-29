# Changelog

All notable changes to QuantForge will be documented in this file.

## [Unreleased]

### Added
- 可选 ATR 固定保护止损与基于止损距离的风险比例整股定仓，止损触发经 Broker 成本模型及 Portfolio 入账。
- 独立 True Range 与 Wilder ATR 指标计算，支持周期配置和明确的暖机期结果。
- MA Cross 示例的静态回测图：收盘价涨跌、实际买卖成交点与组合权益曲线。
- `docs/changes/` 变更记录机制及任务记录模板。
- 固定比例仓位管理 `FixedFractionPositionSizer`，支持整股向下取整和比例配置。

### Changed

### Fixed
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
