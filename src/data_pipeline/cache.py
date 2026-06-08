from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.config_loader import resolve_path


def _safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "_").replace("\\", "_").replace(".", "_")


def cache_path(base_dir: str, market: str, symbol: str, kind: str = "csv") -> Path:
    directory = resolve_path(base_dir) / market.lower()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{_safe_symbol(symbol)}.{kind}"


def read_cached_csv(base_dir: str, market: str, symbol: str) -> pd.DataFrame:
    path = cache_path(base_dir, market, symbol)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["date"])


def write_cached_csv(df: pd.DataFrame, base_dir: str, market: str, symbol: str) -> Path:
    path = cache_path(base_dir, market, symbol)
    data = df.copy()
    if "date" in data.columns:
        data["date"] = pd.to_datetime(data["date"]).dt.strftime("%Y-%m-%d")
    data.to_csv(path, index=False)
    return path


def merge_incremental(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    frames = [df for df in [existing, incoming] if df is not None and not df.empty]
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.drop_duplicates(subset=["date", "symbol"], keep="last")
    return merged.sort_values(["symbol", "date"]).reset_index(drop=True)


def next_start_date(existing: pd.DataFrame, fallback_start: str) -> str:
    if existing.empty or "date" not in existing.columns:
        return fallback_start
    max_date = pd.to_datetime(existing["date"]).max()
    if pd.isna(max_date):
        return fallback_start
    return (max_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
