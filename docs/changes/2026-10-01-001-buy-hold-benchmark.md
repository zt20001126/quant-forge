# Buy & Hold Benchmark 与策略绩效对比

## 基本信息

- 日期：2026-10-01
- 类型：Feature / Test / Docs
- 影响范围：Analytics、结果展示、示例；V0.2 最小增量记入 Unreleased，未调整 0.1.0 包版本。

## 变更背景

单独的策略收益不能说明相对被动持有的表现。增加同资金、同标的和完整回测区间的 Buy & Hold，支持研究验证而不扩展交易系统。

## 变更内容

- 新增冻结的基准权益点、Buy & Hold 结果和策略／基准对比报告。
- 基准按首根 Open 满仓理论小数股、每日 Close 估值，包含暖机期与首日收益；不计佣金、滑点、利息、分红，不强制末日卖出。
- 提取 calculate_equity_performance，calculate_performance 保留签名并复用原公式。
- 对比报告拒绝不同长度、日期、标的及 Close；初始资金来自策略结果。
- 两种图表接收可选关键字 benchmark，显示无成本 Buy & Hold 权益曲线，保留原绘图调用方式。
- 新增 run_benchmark_example，固定一次 CSV 读取；原 run_example 返回接口保持兼容。
- 新增手算、边界、对齐、无未来信息、无副作用与 CSV／图表集成测试。原图表测试用显式 Sequence 类型说明适配 Matplotlib 宽泛返回类型，保留原断言。

## 涉及文件

- `quant/analytics/benchmark.py`
- `quant/analytics/report.py`
- `quant/analytics/metrics.py`
- `quant/analytics/__init__.py`
- `quant/visualization/backtest_plot.py`
- `quant/visualization/interactive_backtest_plot.py`
- `examples/ma_cross_backtest.py`
- `tests/unit/test_benchmark.py`
- `tests/unit/test_visualization.py`
- `tests/integration/test_benchmark_comparison.py`
- `README.md`
- `docs/architecture.md`
- `docs/V0.1_TODO.md`
- `CHANGELOG.md`
- 本记录。

## 设计决策

基准是分析层的理论价格曲线，不生成虚构订单或 Trade，不维护第二个 Portfolio。Engine、Strategy、Broker、Portfolio、Risk 和 BacktestResult 未修改。Analytics 依赖领域 Bar 与只读结果；Visualization 只读取基准，不反向参与交易，无循环依赖。

双方使用初始资金到首日收盘的收益周期、252 日年化、含初始资金峰值的负数回撤及样本标准差 Sharpe，且使用同一无风险利率。策略有实际配置成本和整股约束，理论基准没有；输出明确标注差异，不将收益差称为 Alpha。

应用层固定同一份行情，因为 BacktestResult 不保存 Open 等完整 OHLC；事后日期与 Close 核对无法证明完整输入一致。不增加行情归档或指纹抽象。

## 测试与验证

- `conda run -n agent python --version`：Python 3.10.20。
- `conda run -n agent python -m pytest -q`：137 passed，30 subtests passed。
- `conda run -n agent python -m ruff check .`：All checks passed。
- `conda run -n agent python -m mypy`：Success，53 source files。
- `conda run -n agent python -c "from examples.ma_cross_backtest import run_benchmark_example; from dataclasses import asdict; r = run_benchmark_example('data/stock_real.csv'); print('bars:', len(r.strategy_result.equity_curve), 'trades:', len(r.strategy_result.trades)); print('Strategy:', asdict(r.strategy_metrics)); print('Benchmark:', asdict(r.benchmark_metrics))"`：成功，507 根 Bar、31 笔策略交易；策略总收益约 46.17%，基准约 152.77%。
- 首轮完整测试的资金缩放用例因浮点尾数精确比较失败，改为容差比较；静态检查发现 Matplotlib 测试返回类型问题，已修正。以上列出最终通过结果。
- `git diff --check`：通过；README、架构、TODO、CHANGELOG 和本记录的 10 个本地 Markdown 链接目标全部存在，阶段依赖已核对。
- 静态图使用 Agg 后端、交互图检查 trace；未手动验证浏览器交互操作。

## 潜在影响

旧回测与绩效入口保持兼容；不改变策略 T+1 Open 成交、账户所有权、佣金／滑点规则或 ATR 保护止损。共享绩效计算中的空曲线、零值、无波动和溢出语义保留。

单日年化可能非常大并触发既有溢出校验；缺交易日仍按观察到的 Bar 数年化；未处理公司行为，不能视为含分红总回报基准。已有未跟踪行情 CSV 不属于本次修改。

## 后续事项

成本一致的可执行基准、外部指数、复权／公司行为和更多比较指标留待明确需求后实现；不属于本次未完成项。
