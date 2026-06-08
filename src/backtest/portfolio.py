from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.statistics import summarize_symbol


def build_equal_weight_portfolio(df: pd.DataFrame, market: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return_cols = ["overnight_return", "intraday_return", "close_to_close_return"]
    data = df.dropna(subset=return_cols).copy()
    portfolio = data.groupby("date", as_index=False)[return_cols].mean()
    portfolio["market"] = market.upper()
    portfolio["symbol"] = f"{market.upper()}_EQUAL_WEIGHT"
    portfolio["name"] = f"{market.upper()} equal-weight portfolio"
    portfolio["asset_type"] = "portfolio"
    portfolio = portfolio.sort_values("date").reset_index(drop=True)
    for source_col, target_col in [
        ("overnight_return", "overnight_cum_return"),
        ("intraday_return", "intraday_cum_return"),
        ("close_to_close_return", "close_to_close_cum_return"),
    ]:
        portfolio[target_col] = np.exp(portfolio[source_col].fillna(0).cumsum()) - 1
    return portfolio


def summarize_portfolio(
    df: pd.DataFrame,
    market: str,
    trading_days: int,
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> dict:
    portfolio = build_equal_weight_portfolio(df, market)
    if portfolio.empty:
        return {}
    return summarize_symbol(portfolio, trading_days, n_bootstrap, seed)
