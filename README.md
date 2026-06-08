# Overnight Intraday Backtest

用于验证美国股票市场和中国 A 股市场中，股票、ETF、指数是否长期存在“隔夜收益显著高于日内收益”的统计现象。

本项目只做历史收益分解、统计检验和报告生成，不包含自动交易、下单、择时信号或投资建议。

## 回测公式

- 隔夜收益：`overnight_return_t = ln(open_t / close_{t-1})`
- 日内收益：`intraday_return_t = ln(close_t / open_t)`
- 收盘到收盘收益：`close_to_close_return_t = ln(close_t / close_{t-1})`

理论上：

```text
close_to_close_return_t ~= overnight_return_t + intraday_return_t
```

代码会在 `src/backtest/returns.py` 中校验该恒等式，误差过大时输出 warning。

## 数据源

- 美国市场：Twelve Data API。API Key 从环境变量 `TWELVE_DATA_API_KEY` 读取，不写入代码或配置文件。
- 中国 A 股市场：baostock，不需要 API Key。
- 标准字段：`date, market, symbol, name, open, high, low, close, volume, source`。

A 股复权参数位于 `config/config.yaml`：

```yaml
markets:
  cn:
    adjustflag: "3"
```

baostock 口径：`1=后复权`，`2=前复权`，`3=不复权`。默认使用不复权价格验证真实可交易价格。

## 本地运行

安装依赖：

```bash
pip install -r requirements.txt
```

配置 Twelve Data API Key：

```bash
export TWELVE_DATA_API_KEY="your_api_key"
```

Windows PowerShell：

```powershell
$env:TWELVE_DATA_API_KEY="your_api_key"
```

全量运行：

```bash
python -m src.main --market all --start 2000-01-01 --end today
```

只跑美国市场：

```bash
python -m src.main --market us --start 2000-01-01 --end today
```

只跑中国市场：

```bash
python -m src.main --market cn --start 2005-01-01 --end today
```

使用缓存，不重新拉取：

```bash
python -m src.main --market all --use-cache
```

强制刷新：

```bash
python -m src.main --market all --refresh
```

快速测试模式：

```bash
python -m src.main --market all --quick
```

quick 模式只使用少量标的和最近三年数据，适合 GitHub Actions smoke test。

## 输出文件

报告输出到 `reports/`：

- `summary_us.csv`
- `summary_cn.csv`
- `portfolio_summary_us.csv`
- `portfolio_summary_cn.csv`
- `by_year_summary.csv`
- `rolling_3y_summary.csv`
- `rolling_5y_summary.csv`
- `report.md`
- `figures/*.png`

数据缓存输出到：

- `data/raw/`
- `data/processed/`

仓库通过 `.gitignore` 排除大体积缓存数据和生成报告，避免把历史行情提交到 Git。

## GitHub Actions

工作流文件：`.github/workflows/backtest.yml`

支持：

- `workflow_dispatch` 手动触发
- 每周一自动运行
- Ubuntu + Python 3.11
- 安装 `requirements.txt`
- 使用 `actions/cache` 缓存 `data/`
- 运行 pytest
- 运行 quick smoke test
- 运行正式回测
- 上传 `reports/` 为 artifact

### 配置 GitHub Secrets

进入 GitHub 仓库：

1. 打开 `Settings`
2. 打开 `Secrets and variables`
3. 选择 `Actions`
4. 新增 secret：`TWELVE_DATA_API_KEY`
5. 值填写 Twelve Data API Key

工作流通过环境变量读取该 secret，不会打印 API Key。

### 查看 artifacts

1. 打开仓库的 `Actions`
2. 选择一次运行记录
3. 在页面底部找到 `Artifacts`
4. 下载 `overnight-intraday-reports`

## 修改标的池

美国市场标的：

```text
config/symbols_us.csv
```

中国市场标的：

```text
config/symbols_cn.csv
```

CSV 必须包含：

```text
market,symbol,name,asset_type
```

指数和个股通过 `asset_type` 区分，报告中不会把指数结论和个股结论混成一个结论。

## 统计检验

项目实现：

- Welch 单侧 t-test：检验 `overnight_mean > intraday_mean`
- bootstrap 均值差置信区间
- Mann-Whitney U test
- 年度分组统计
- 3 年滚动统计
- 5 年滚动统计

如果样本不足、p-value 不显著或数据质量不足，报告会直接写明：当前数据不足以推断隔夜收益显著高于日内收益。

## 为什么没有直接使用现成回测框架？

- Backtrader 更适合完整交易策略和订单撮合。
- vectorbt 更适合大规模参数化策略。
- backtesting.py 更适合交易策略验证。
- 本项目重点是隔夜/日内收益分解和统计验证，不涉及订单、滑点、撮合和仓位管理，因此 Pandas 更直接、更透明。

## 已知局限

- 隔夜收益对开盘价质量非常敏感，异常 open/close 会被剔除。
- Twelve Data 日线数据可能处理拆股，但分红对隔夜收益可能有影响。本版本优先验证 open-close 分解现象，分红完全复权处理可能不足，后续版本可接入 splits/dividends 进一步修正。
- A 股存在停牌、涨跌停、复权方式差异，不同 `adjustflag` 可能影响结果。
- 数据源的历史修订、指数口径和个股存续期会影响统计结论。
- 显著性结果只代表历史样本中的统计关系，不代表未来收益。

## 不构成投资建议

本项目仅用于历史数据统计验证与研究复现，不构成任何投资建议、交易建议或收益承诺。
