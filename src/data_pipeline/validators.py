from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationResult:
    df: pd.DataFrame
    issues: list[str] = field(default_factory=list)


def validate_ohlcv(df: pd.DataFrame, symbol: str | None = None) -> ValidationResult:
    label = symbol or (str(df["symbol"].iloc[0]) if "symbol" in df.columns and not df.empty else "unknown")
    if df.empty:
        return ValidationResult(df.copy(), [f"{label}: empty data"])

    data = df.copy()
    issues: list[str] = []

    before = len(data)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"])
    dropped_dates = before - len(data)
    if dropped_dates:
        issues.append(f"{label}: dropped {dropped_dates} rows with invalid date")

    duplicate_count = data.duplicated(subset=["date", "symbol"], keep="last").sum()
    if duplicate_count:
        issues.append(f"{label}: removed {duplicate_count} duplicate trading-day rows")
        data = data.drop_duplicates(subset=["date", "symbol"], keep="last")

    required_price_cols = ["open", "high", "low", "close"]
    for col in required_price_cols + ["volume"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    before = len(data)
    data = data.dropna(subset=required_price_cols)
    missing_count = before - len(data)
    if missing_count:
        issues.append(f"{label}: dropped {missing_count} rows with missing OHLC values")

    before = len(data)
    valid_prices = (data[required_price_cols] > 0).all(axis=1)
    data = data.loc[valid_prices].copy()
    invalid_count = before - len(data)
    if invalid_count:
        issues.append(f"{label}: dropped {invalid_count} rows with non-positive OHLC prices")

    before = len(data)
    high_ok = data["high"] >= data[["open", "close", "low"]].max(axis=1)
    low_ok = data["low"] <= data[["open", "close", "high"]].min(axis=1)
    data = data.loc[high_ok & low_ok].copy()
    range_count = before - len(data)
    if range_count:
        issues.append(f"{label}: dropped {range_count} rows with inconsistent high/low range")

    data = data.sort_values(["symbol", "date"]).reset_index(drop=True)
    return ValidationResult(data, issues)
