# 增加 Wilder ATR 指标计算

## 基本信息

- 日期：2026-09-29
- 类型：Feature / Test / Docs
- 影响范围：纯指标计算、公开导出、指标测试与能力文档。

## 变更背景

项目已有 OHLCV Bar 与 SMA，但缺少 True Range / ATR。独立 ATR 指标是后续策略和风险定仓学习的基础；本次只增加可测试的计算能力。

## 变更内容

- 新增 `true_range(bars)`：验证单标的、严格递增时间；首根使用 High − Low，后续 TR 纳入前收盘跳空。
- 新增 `average_true_range(bars, period)`：首个 ATR 为 period 个 TR 的 SMA，后续按 Wilder 公式平滑；暖机结果为 None。
- 从 `quant.indicators` 导出两个函数。
- 增加手算测试，覆盖跳空、周期1、Wilder 递推、暖机、空输入、非法周期、乱序和混合标的。
- 更新 README、当前架构、V0.1 Phase 4 与 Unreleased 记录，说明 ATR 尚未接入策略/止损。

## 涉及文件

- `quant/indicators/average_true_range.py`
- `quant/indicators/__init__.py`
- `tests/unit/test_average_true_range.py`
- `README.md`
- `docs/architecture.md`
- `docs/V0.1_TODO.md`
- `CHANGELOG.md`

## 设计决策

- 使用 Wilder 平滑，首个 ATR 以周期 TR 的简单平均初始化；TR 首根使用 High − Low。这样算法和暖机结果确定且可手算。
- 指标要求单标的、时间严格递增，避免把多个证券或乱序输入误当同一条价格路径。
- ATR 函数只读取传入 Bar 序列，不接入策略、风险定仓、Portfolio 或 Engine。

## 测试与验证

- 修复前 `python -m pytest -q tests/unit/test_average_true_range.py`：收集失败，因待实现的指标模块尚不存在。
- `python -m pytest -q tests/unit/test_average_true_range.py`：7 passed。
- `python -m pytest -q`：37 passed。
- `conda run -n agent python -m ruff check quant/indicators tests/unit/test_average_true_range.py`：通过。
- `conda run -n agent python -m mypy quant`：通过，检查 31 个源文件。
- `git diff --check`：通过；新增文档检查无尾随空白。

## 潜在影响

新增 `quant.indicators.true_range` 与 `quant.indicators.average_true_range` 公开函数，无第三方依赖；现有 SMA/策略/成交行为不变。ATR 当前不能自动生成止损或风险订单。

## 后续事项

若下一步实现 ATR 定仓或止损，须单独定义执行时间、跳空成交、订单去重和账户入账规则，并增加端到端测试。
