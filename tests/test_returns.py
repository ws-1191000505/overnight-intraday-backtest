import numpy as np
import pandas as pd
import pytest

from src.backtest.returns import compute_cumulative_returns, compute_log_returns, validate_return_identity


def sample_ohlc() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
            "market": ["US", "US", "US"],
            "symbol": ["TEST", "TEST", "TEST"],
            "name": ["Test", "Test", "Test"],
            "open": [100.0, 103.0, 105.0],
            "high": [102.0, 106.0, 108.0],
            "low": [99.0, 102.0, 104.0],
            "close": [101.0, 104.0, 107.0],
            "volume": [1000, 1100, 1200],
            "source": ["unit", "unit", "unit"],
        }
    )


def test_log_return_identity() -> None:
    returns = compute_log_returns(sample_ohlc())
    diff = (
        returns["overnight_return"]
        + returns["intraday_return"]
        - returns["close_to_close_return"]
    ).dropna()
    assert np.allclose(diff, 0.0)
    assert validate_return_identity(returns)


def test_first_day_overnight_is_nan() -> None:
    returns = compute_log_returns(sample_ohlc())
    assert pd.isna(returns.loc[0, "overnight_return"])


def test_open_zero_raises() -> None:
    data = sample_ohlc()
    data.loc[1, "open"] = 0
    with pytest.raises(ValueError, match="non-positive"):
        compute_log_returns(data)


def test_cumulative_returns_are_created() -> None:
    returns = compute_cumulative_returns(compute_log_returns(sample_ohlc()))
    assert {"overnight_cum_return", "intraday_cum_return", "close_to_close_cum_return"}.issubset(
        returns.columns
    )
