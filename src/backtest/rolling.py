from __future__ import annotations

import pandas as pd

from src.backtest.statistics import summarize_symbol


def summarize_by_year(
    df: pd.DataFrame,
    trading_days_by_market: dict[str, int],
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> pd.DataFrame:
    rows: list[dict] = []
    if df.empty:
        return pd.DataFrame()
    data = df.copy()
    data["year"] = pd.to_datetime(data["date"]).dt.year
    for (market, symbol, year), group in data.groupby(["market", "symbol", "year"]):
        summary = summarize_symbol(
            group,
            trading_days=trading_days_by_market.get(str(market).lower(), 252),
            n_bootstrap=n_bootstrap,
            seed=seed,
        )
        if summary:
            summary["period"] = str(year)
            summary["period_type"] = "year"
            rows.append(summary)
    return pd.DataFrame(rows)


def summarize_rolling_years(
    df: pd.DataFrame,
    years: int,
    trading_days_by_market: dict[str, int],
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> pd.DataFrame:
    rows: list[dict] = []
    if df.empty:
        return pd.DataFrame()
    data = df.copy()
    data["year"] = pd.to_datetime(data["date"]).dt.year
    min_year = int(data["year"].min())
    max_year = int(data["year"].max())
    for start_year in range(min_year, max_year - years + 2):
        end_year = start_year + years - 1
        window = data[(data["year"] >= start_year) & (data["year"] <= end_year)]
        for (market, symbol), group in window.groupby(["market", "symbol"]):
            summary = summarize_symbol(
                group,
                trading_days=trading_days_by_market.get(str(market).lower(), 252),
                n_bootstrap=n_bootstrap,
                seed=seed,
            )
            if summary:
                summary["period"] = f"{start_year}-{end_year}"
                summary["period_type"] = f"rolling_{years}y"
                rows.append(summary)
    return pd.DataFrame(rows)
