# 交互式回测可视化

## 背景

静态价格图用密集涨跌日散点干扰 Close 与真实成交标记的阅读，且不能逐日检查 OHLCV、成交、权益与回撤。

## 实现

- 保留 Matplotlib `plot_backtest`，移除上涨日/下跌日散点。
- 新增独立 Plotly `plot_interactive_backtest`，以共享时间轴呈现价格、Portfolio Equity、Drawdown，支持缩放、平移和日期区间滑块。
- 悬停显示 Bar OHLCV；实际 Trade 显示方向、成交价、数量、佣金和信号日。
- 指标线与止损线通过可选序列传入，且验证长度与 Bars 一致。
- 增加 Plotly 运行依赖，更新 README、架构说明和可视化测试。
- MA Cross 示例默认打开 Plotly 交互图，静态绘图 API 保持不变。

## 数据与边界

`Trade` 没有独立滑点金额字段，成交价已经包含滑点影响，图中不推算滑点数额。策略不暴露逐日指标，`BacktestResult` 也不保存止损价时间序列；调用方未传值时不显示对应曲线。没有修改策略、Broker、Portfolio 或 Engine。

## 验证

- `python -m pytest -q`：108 passed。
- `git diff --check`：通过。
- `python -m ruff check .`：未运行，当前 Python 环境缺少 `ruff` 模块。
- `python -m mypy`：未运行，当前 Python 环境缺少 `mypy` 模块。

## 涉及文件

- `quant/visualization/backtest_plot.py`
- `quant/visualization/interactive_backtest_plot.py`
- `quant/visualization/__init__.py`
- `examples/ma_cross_backtest.py`
- `tests/unit/test_visualization.py`
- `pyproject.toml`
- `README.md`
- `docs/architecture.md`
- `docs/V0.1_TODO.md`
