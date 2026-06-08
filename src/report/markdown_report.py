from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _fmt_pct(value: Any) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.2%}"


def _market_result(summary: pd.DataFrame, market: str) -> str:
    if summary.empty:
        return "当前没有可用结果。\n"
    rows = []
    display_cols = [
        "symbol",
        "asset_type",
        "sample_trading_days",
        "overnight_annual_return",
        "intraday_annual_return",
        "mean_diff",
        "p_value",
    ]
    for _, row in summary[display_cols].iterrows():
        rows.append(
            "| {symbol} | {asset_type} | {days} | {overnight} | {intraday} | {diff:.6f} | {p_value:.4g} |".format(
                symbol=row["symbol"],
                asset_type=row["asset_type"],
                days=int(row["sample_trading_days"]),
                overnight=_fmt_pct(row["overnight_annual_return"]),
                intraday=_fmt_pct(row["intraday_annual_return"]),
                diff=row["mean_diff"],
                p_value=row["p_value"] if pd.notna(row["p_value"]) else float("nan"),
            )
        )
    table = "\n".join(rows)
    return (
        "| 标的 | 类型 | 样本交易日 | 隔夜年化收益 | 日内年化收益 | 均值差 | Welch p-value |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n"
        f"{table}\n"
    )


def _conclusion_for_market(summary: pd.DataFrame, market: str) -> str:
    if summary.empty:
        return f"- {market.upper()}：当前没有可用样本。"
    enough = summary["sample_trading_days"].fillna(0) >= 60
    significant = summary["p_value"].fillna(1) < 0.05
    positive = summary["mean_diff"].fillna(-1) > 0
    count = int((enough & significant & positive).sum())
    total = int(len(summary))
    if count == 0:
        return f"- {market.upper()}：当前数据不足以推断隔夜收益显著高于日内收益。"
    return f"- {market.upper()}：{count}/{total} 个标的在 Welch 单侧检验下呈现隔夜均值显著高于日内均值。"


def write_report(
    output_path: str | Path,
    *,
    summaries: dict[str, pd.DataFrame],
    portfolio_summaries: dict[str, pd.DataFrame],
    by_year_summary: pd.DataFrame,
    rolling_3y_summary: pd.DataFrame,
    rolling_5y_summary: pd.DataFrame,
    figures: list[Path],
    config: dict,
    validation_issues: list[str],
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    all_summaries = [df for df in summaries.values() if not df.empty]
    combined = pd.concat(all_summaries, ignore_index=True) if all_summaries else pd.DataFrame()
    if combined.empty:
        sample_range = "无可用样本"
        symbol_count = 0
    else:
        sample_range = f"{combined['start_date'].min()} 至 {combined['end_date'].max()}"
        symbol_count = int(combined["symbol"].nunique())

    cn_adjustflag = config["markets"]["cn"].get("adjustflag", "3")
    adjust_text = {"1": "后复权", "2": "前复权", "3": "不复权"}.get(str(cn_adjustflag), str(cn_adjustflag))

    figure_lines = "\n".join(f"- `{fig.as_posix()}`" for fig in figures) or "- 暂无图表输出。"
    issue_lines = "\n".join(f"- {item}" for item in validation_issues[:50]) or "- 未记录到数据质量剔除项。"

    portfolio_lines = []
    for market, df in portfolio_summaries.items():
        if df.empty:
            portfolio_lines.append(f"- {market.upper()}：无组合结果。")
            continue
        row = df.iloc[0]
        portfolio_lines.append(
            f"- {market.upper()} 等权组合：隔夜年化 {_fmt_pct(row['overnight_annual_return'])}，"
            f"日内年化 {_fmt_pct(row['intraday_annual_return'])}，"
            f"Welch p-value {row['p_value']:.4g}。"
        )

    text = f"""# 隔夜收益 / 日内收益回测统计报告

## 数据源说明

- 美国市场：Twelve Data API，API Key 通过环境变量 `TWELVE_DATA_API_KEY` 读取，代码和配置文件不保存密钥。
- 中国 A 股市场：baostock，不需要 API Key。
- 标准字段：`date, market, symbol, name, open, high, low, close, volume, source`。
- A 股复权口径：当前配置 `adjustflag={cn_adjustflag}`，含义为{adjust_text}。

## 回测口径

- 隔夜收益：`ln(open_t / close_(t-1))`。
- 日内收益：`ln(close_t / open_t)`。
- 收盘到收盘收益：`ln(close_t / close_(t-1))`。
- 校验恒等式：`close_to_close_return ≈ overnight_return + intraday_return`。
- US 年化交易日参数：{config['markets']['us'].get('trading_days', 252)}。
- CN 年化交易日参数：{config['markets']['cn'].get('trading_days', 244)}。

## 样本区间

- 样本区间：{sample_range}
- 标的数量：{symbol_count}

## 核心结论

事实：
{_conclusion_for_market(summaries.get('us', pd.DataFrame()), 'us')}
{_conclusion_for_market(summaries.get('cn', pd.DataFrame()), 'cn')}

判断：
- 是否能推断“隔夜收益显著高于日内收益”，以每个标的和市场等权组合的均值差、Welch 单侧 t-test、bootstrap 置信区间共同判断。
- 指数和个股分开统计，不把指数结果和个股结果混成一个结论。

假设：
- 若观察到显著差异，可能与交易时段信息释放、开盘集合竞价、风险补偿、分红拆股处理、停牌和涨跌停制度等因素有关，需在后续研究中单独验证。

## 美国市场结果

{_market_result(summaries.get('us', pd.DataFrame()), 'us')}

## 中国市场结果

{_market_result(summaries.get('cn', pd.DataFrame()), 'cn')}

## 市场组合结果

{chr(10).join(portfolio_lines) if portfolio_lines else "- 暂无组合结果。"}

## 隔夜收益是否显著高于日内收益

- 当样本不足、p-value 不显著、bootstrap 置信区间未稳定大于 0，或数据质量不足时，结论应为：当前数据不足以推断隔夜收益显著高于日内收益。
- 本报告默认使用 Welch 单侧 t-test 检验 `overnight_mean > intraday_mean`，同时输出 Mann-Whitney U test 和 bootstrap 均值差置信区间。

## 稳健性检验

- 年度分组结果：`reports/by_year_summary.csv`，当前行数 {len(by_year_summary)}。
- 3 年滚动结果：`reports/rolling_3y_summary.csv`，当前行数 {len(rolling_3y_summary)}。
- 5 年滚动结果：`reports/rolling_5y_summary.csv`，当前行数 {len(rolling_5y_summary)}。

## 图表

{figure_lines}

## 数据质量记录

{issue_lines}

## 数据局限

- 隔夜收益对开盘价质量非常敏感，open 或 close 为 0、空值、异常值的记录已剔除并记录。
- 本版本优先验证 open-close 分解现象，分红完全复权处理可能不足，后续版本可接入 splits/dividends 进一步修正。
- A 股存在停牌、涨跌停、复权方式差异，当前报告已记录 baostock 复权参数，但不同复权口径可能影响统计结果。
- Twelve Data 与 baostock 的历史数据修订、指数口径和个股存续期可能带来样本偏差。

## 不构成投资建议声明

本项目仅用于历史数据统计验证与研究复现，不构成任何投资建议、交易建议或收益承诺。
"""
    path.write_text(text, encoding="utf-8")
    return path
