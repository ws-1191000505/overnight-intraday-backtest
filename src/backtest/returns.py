from __future__ import annotations

import logging

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


def compute_log_returns(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    if data.empty:
        return data

    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values(["symbol", "date"]).reset_index(drop=True)
    price_cols = ["open", "close"]
    for col in price_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    invalid = data[price_cols].notna().all(axis=1) & (data[price_cols] <= 0).any(axis=1)
    if invalid.any():
        bad_symbols = sorted(data.loc[invalid, "symbol"].astype(str).unique())
        raise ValueError(f"non-positive open/close prices found for {bad_symbols}")

    data["prev_close"] = data.groupby("symbol")["close"].shift(1)
    data["overnight_return"] = np.log(data["open"] / data["prev_close"])
    data["intraday_return"] = np.log(data["close"] / data["open"])
    data["close_to_close_return"] = np.log(data["close"] / data["prev_close"])
    return data


def compute_cumulative_returns(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    if data.empty:
        return data

    data = data.sort_values(["symbol", "date"]).reset_index(drop=True)
    for source_col, target_col in [
        ("overnight_return", "overnight_cum_return"),
        ("intraday_return", "intraday_cum_return"),
        ("close_to_close_return", "close_to_close_cum_return"),
    ]:
        data[target_col] = (
            data.groupby("symbol")[source_col]
            .transform(lambda s: np.exp(s.fillna(0).cumsum()) - 1)
            .astype(float)
        )
    return data


def validate_return_identity(df: pd.DataFrame, tolerance: float = 1e-8) -> bool:
    if df.empty:
        return True
    required = {"overnight_return", "intraday_return", "close_to_close_return"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"missing return columns: {sorted(missing)}")

    diff = (
        df["close_to_close_return"]
        - df["overnight_return"]
        - df["intraday_return"]
    ).abs()
    max_diff = diff.dropna().max()
    if pd.isna(max_diff):
        return True
    if max_diff > tolerance:
        LOGGER.warning("return identity max diff %.12f exceeds tolerance %.12f", max_diff, tolerance)
        return False
    return True
