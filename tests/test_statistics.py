import numpy as np
import pandas as pd

from src.backtest.statistics import (
    annualized_return,
    annualized_volatility,
    max_drawdown,
    sharpe_ratio,
    welch_ttest_overnight_vs_intraday,
)


def test_annualized_return() -> None:
    returns = pd.Series([0.01, 0.01])
    assert np.isclose(annualized_return(returns, 252), np.exp(2.52) - 1)


def test_annualized_volatility_and_sharpe() -> None:
    returns = pd.Series([0.01, -0.01, 0.02, -0.02])
    vol = annualized_volatility(returns, 252)
    sharpe = sharpe_ratio(returns, trading_days=252)
    assert vol > 0
    assert np.isfinite(sharpe)


def test_max_drawdown() -> None:
    cumulative = pd.Series([0.0, 0.2, 0.1, 0.3, -0.1])
    assert np.isclose(max_drawdown(cumulative), (0.9 / 1.3) - 1)


def test_ttest_output_contains_statistic_and_p_value() -> None:
    df = pd.DataFrame(
        {
            "overnight_return": [0.01, 0.02, 0.015, 0.018],
            "intraday_return": [-0.01, -0.005, 0.0, -0.002],
        }
    )
    result = welch_ttest_overnight_vs_intraday(df)
    assert {"statistic", "p_value"}.issubset(result)
    assert result["p_value"] < 0.05
