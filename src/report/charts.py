from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


def _ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def plot_market_cumulative(portfolio_df: pd.DataFrame, market: str, figures_dir: str | Path) -> Path | None:
    if portfolio_df.empty:
        return None
    out_dir = _ensure_dir(figures_dir)
    fig, ax = plt.subplots(figsize=(11, 6))
    data = portfolio_df.sort_values("date")
    ax.plot(data["date"], data["overnight_cum_return"], label="Overnight")
    ax.plot(data["date"], data["intraday_cum_return"], label="Intraday")
    ax.plot(data["date"], data["close_to_close_cum_return"], label="Close-to-close")
    ax.set_title(f"{market.upper()} cumulative returns")
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative return")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.autofmt_xdate()
    path = out_dir / f"{market.lower()}_cumulative_returns.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_annual_bars(by_year_summary: pd.DataFrame, market: str, figures_dir: str | Path) -> Path | None:
    if by_year_summary.empty:
        return None
    data = by_year_summary[
        (by_year_summary["market"].str.upper() == market.upper())
        & (by_year_summary["asset_type"] == "portfolio")
    ].copy()
    if data.empty:
        return None
    data["period"] = data["period"].astype(str)
    out_dir = _ensure_dir(figures_dir)
    fig, ax = plt.subplots(figsize=(12, 6))
    x = range(len(data))
    width = 0.42
    ax.bar([i - width / 2 for i in x], data["overnight_annual_return"], width=width, label="Overnight")
    ax.bar([i + width / 2 for i in x], data["intraday_annual_return"], width=width, label="Intraday")
    ax.set_xticks(list(x))
    ax.set_xticklabels(data["period"], rotation=45, ha="right")
    ax.set_title(f"{market.upper()} annual overnight vs intraday returns")
    ax.set_ylabel("Annualized return")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    path = out_dir / f"{market.lower()}_annual_returns.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_mean_diff_ranking(summary: pd.DataFrame, market: str, figures_dir: str | Path) -> Path | None:
    if summary.empty:
        return None
    data = summary[summary["market"].str.upper() == market.upper()].copy()
    if data.empty:
        return None
    data = data.sort_values("mean_diff", ascending=True)
    out_dir = _ensure_dir(figures_dir)
    fig, ax = plt.subplots(figsize=(10, max(5, len(data) * 0.42)))
    labels = data["symbol"].astype(str)
    ax.barh(labels, data["mean_diff"])
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title(f"{market.upper()} overnight mean minus intraday mean")
    ax.set_xlabel("Mean difference")
    ax.grid(True, axis="x", alpha=0.3)
    path = out_dir / f"{market.lower()}_mean_diff_ranking.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_pvalue_distribution(summary: pd.DataFrame, market: str, figures_dir: str | Path) -> Path | None:
    if summary.empty:
        return None
    data = summary[summary["market"].str.upper() == market.upper()]["p_value"].dropna()
    if data.empty:
        return None
    out_dir = _ensure_dir(figures_dir)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(data, bins=20, edgecolor="white")
    ax.axvline(0.05, color="red", linestyle="--", linewidth=1, label="0.05")
    ax.set_title(f"{market.upper()} p-value distribution")
    ax.set_xlabel("Welch t-test p-value")
    ax.set_ylabel("Count")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    path = out_dir / f"{market.lower()}_pvalue_distribution.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def create_market_charts(
    portfolio_curves: dict[str, pd.DataFrame],
    summaries: dict[str, pd.DataFrame],
    by_year_summary: pd.DataFrame,
    figures_dir: str | Path,
) -> list[Path]:
    paths: list[Path] = []
    for market, curve in portfolio_curves.items():
        for path in [
            plot_market_cumulative(curve, market, figures_dir),
            plot_annual_bars(by_year_summary, market, figures_dir),
            plot_mean_diff_ranking(summaries.get(market, pd.DataFrame()), market, figures_dir),
            plot_pvalue_distribution(summaries.get(market, pd.DataFrame()), market, figures_dir),
        ]:
            if path is not None:
                paths.append(path)
    return paths
