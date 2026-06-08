from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

LOGGER = logging.getLogger(__name__)


@dataclass
class TwelveDataClient:
    api_key: str | None = None
    request_interval_seconds: float = 8.0
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    base_url: str = "https://api.twelvedata.com/time_series"

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.getenv("TWELVE_DATA_API_KEY")
        self._last_request_at = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_at
        wait_for = self.request_interval_seconds - elapsed
        if wait_for > 0:
            time.sleep(wait_for)

    def _fetch_once(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        if not self.api_key:
            raise RuntimeError("TWELVE_DATA_API_KEY is required for US market data")

        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": "1day",
            "start_date": start,
            "end_date": end,
            "outputsize": 5000,
            "order": "ASC",
            "apikey": self.api_key,
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit()
                response = requests.get(self.base_url, params=params, timeout=30)
                self._last_request_at = time.time()
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") == "error":
                    raise RuntimeError(payload.get("message", f"Twelve Data error for {symbol}"))
                values = payload.get("values", [])
                if not values:
                    LOGGER.warning("%s: Twelve Data returned no rows", symbol)
                    return pd.DataFrame()
                return pd.DataFrame(values)
            except Exception as exc:  # noqa: BLE001 - retry boundary
                last_error = exc
                LOGGER.warning(
                    "%s: Twelve Data request failed on attempt %s/%s: %s",
                    symbol,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * attempt)

        raise RuntimeError(f"{symbol}: Twelve Data request failed") from last_error

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        start_ts = pd.to_datetime(start)
        end_ts = pd.to_datetime(end)
        if start_ts > end_ts:
            return pd.DataFrame()

        frames: list[pd.DataFrame] = []
        chunk_start = start_ts
        while chunk_start <= end_ts:
            chunk_end = min(chunk_start + pd.DateOffset(years=5) - pd.Timedelta(days=1), end_ts)
            frame = self._fetch_once(
                symbol,
                chunk_start.strftime("%Y-%m-%d"),
                chunk_end.strftime("%Y-%m-%d"),
            )
            if not frame.empty:
                frames.append(frame)
            chunk_start = chunk_end + pd.Timedelta(days=1)

        if not frames:
            return pd.DataFrame()
        data = pd.concat(frames, ignore_index=True)
        return data.drop_duplicates(subset=["datetime"], keep="last")
