from __future__ import annotations

import pandas as pd


STANDARD_COLUMNS = [
    "date",
    "market",
    "symbol",
    "name",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
]


def normalize_ohlcv(
    df: pd.DataFrame,
    *,
    market: str,
    symbol: str,
    name: str,
    source: str,
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    data = df.copy()
    data.columns = [str(col).lower() for col in data.columns]
    rename_map = {"datetime": "date", "code": "symbol"}
    data = data.rename(columns=rename_map)

    if "date" not in data.columns:
        raise ValueError(f"{symbol}: missing date column")

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in data.columns:
            data[col] = pd.NA
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data["market"] = market.upper()
    data["symbol"] = symbol
    data["name"] = name
    data["source"] = source

    data = data[STANDARD_COLUMNS]
    data = data.dropna(subset=["date"])
    data = data.drop_duplicates(subset=["date", "symbol"], keep="last")
    return data.sort_values(["symbol", "date"]).reset_index(drop=True)
