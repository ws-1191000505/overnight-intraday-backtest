from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_config(config_path: str | Path = "config/config.yaml") -> dict[str, Any]:
    with resolve_path(config_path).open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_symbols(market: str) -> pd.DataFrame:
    market = market.lower()
    if market not in {"us", "cn"}:
        raise ValueError("market must be 'us' or 'cn'")
    path = resolve_path(f"config/symbols_{market}.csv")
    symbols = pd.read_csv(path)
    required = {"market", "symbol", "name", "asset_type"}
    missing = required.difference(symbols.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")
    return symbols
