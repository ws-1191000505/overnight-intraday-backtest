import pandas as pd

from src.data_pipeline.validators import validate_ohlcv


def base_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02", "2024-01-03", "2024-01-04"],
            "market": ["US"] * 4,
            "symbol": ["TEST"] * 4,
            "name": ["Test"] * 4,
            "open": [100.0, 101.0, 102.0, 0.0],
            "high": [102.0, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 98.0],
            "close": [101.0, 102.0, None, 104.0],
            "volume": [1000, 1000, 1000, 1000],
            "source": ["unit"] * 4,
        }
    )


def test_duplicate_dates_are_removed() -> None:
    result = validate_ohlcv(base_data())
    assert result.df["date"].duplicated().sum() == 0
    assert any("duplicate" in issue for issue in result.issues)


def test_missing_values_are_removed() -> None:
    result = validate_ohlcv(base_data())
    assert result.df["close"].isna().sum() == 0
    assert any("missing OHLC" in issue for issue in result.issues)


def test_abnormal_prices_are_removed() -> None:
    result = validate_ohlcv(base_data())
    assert (result.df[["open", "high", "low", "close"]] <= 0).sum().sum() == 0
    assert any("non-positive" in issue for issue in result.issues)
