from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

LOGGER = logging.getLogger(__name__)


@dataclass
class BaoStockClient:
    adjustflag: str = "3"

    def __post_init__(self) -> None:
        import baostock as bs

        self.bs = bs
        login_result = self.bs.login()
        if login_result.error_code != "0":
            raise RuntimeError(f"baostock login failed: {login_result.error_msg}")

    def close(self) -> None:
        self.bs.logout()

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        fields = "date,code,open,high,low,close,volume"
        rs = self.bs.query_history_k_data_plus(
            symbol,
            fields,
            start_date=start,
            end_date=end,
            frequency="d",
            adjustflag=self.adjustflag,
        )
        if rs.error_code != "0":
            raise RuntimeError(f"{symbol}: baostock query failed: {rs.error_msg}")

        rows: list[list[str]] = []
        while rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            LOGGER.warning("%s: baostock returned no rows", symbol)
            return pd.DataFrame(columns=fields.split(","))
        return pd.DataFrame(rows, columns=rs.fields)
