from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

try:
    from scipy import stats
except ImportError:  # pragma: no cover - exercised only in minimal local runtimes
    stats = None


def _clean_returns(daily_returns: pd.Series | np.ndarray) -> pd.Series:
    series = pd.Series(daily_returns, dtype="float64").replace([np.inf, -np.inf], np.nan)
    return series.dropna()


def annualized_return(daily_returns: pd.Series | np.ndarray, trading_days: int) -> float:
    returns = _clean_returns(daily_returns)
    if returns.empty:
        return np.nan
    return float(np.exp(returns.mean() * trading_days) - 1)


def annualized_volatility(daily_returns: pd.Series | np.ndarray, trading_days: int) -> float:
    returns = _clean_returns(daily_returns)
    if len(returns) < 2:
        return np.nan
    return float(returns.std(ddof=1) * math.sqrt(trading_days))


def sharpe_ratio(
    daily_returns: pd.Series | np.ndarray,
    risk_free_rate: float = 0,
    trading_days: int = 252,
) -> float:
    returns = _clean_returns(daily_returns)
    vol = annualized_volatility(returns, trading_days)
    if not np.isfinite(vol) or vol == 0:
        return np.nan
    annual_excess = returns.mean() * trading_days - risk_free_rate
    return float(annual_excess / vol)


def max_drawdown(cumulative_returns: pd.Series | np.ndarray) -> float:
    cumulative = _clean_returns(cumulative_returns)
    if cumulative.empty:
        return np.nan
    equity = 1 + cumulative
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    return float(drawdown.min())


def win_rate(daily_returns: pd.Series | np.ndarray) -> float:
    returns = _clean_returns(daily_returns)
    if returns.empty:
        return np.nan
    return float((returns > 0).mean())


def welch_ttest_overnight_vs_intraday(df: pd.DataFrame) -> dict[str, float]:
    overnight = _clean_returns(df["overnight_return"])
    intraday = _clean_returns(df["intraday_return"])
    if len(overnight) < 2 or len(intraday) < 2:
        return {"statistic": np.nan, "p_value": np.nan}
    if stats is None:
        n1, n2 = len(overnight), len(intraday)
        v1, v2 = overnight.var(ddof=1), intraday.var(ddof=1)
        se = math.sqrt(v1 / n1 + v2 / n2)
        if se == 0:
            return {"statistic": np.nan, "p_value": np.nan}
        statistic = float((overnight.mean() - intraday.mean()) / se)
        # Normal-tail fallback for local smoke tests. CI installs scipy and uses the exact t distribution.
        p_value = 0.5 * math.erfc(statistic / math.sqrt(2))
        return {"statistic": statistic, "p_value": float(p_value)}
    result = stats.ttest_ind(overnight, intraday, equal_var=False, alternative="greater")
    return {"statistic": float(result.statistic), "p_value": float(result.pvalue)}


def mann_whitney_overnight_vs_intraday(df: pd.DataFrame) -> dict[str, float]:
    overnight = _clean_returns(df["overnight_return"])
    intraday = _clean_returns(df["intraday_return"])
    if len(overnight) < 2 or len(intraday) < 2 or stats is None:
        return {"statistic": np.nan, "p_value": np.nan}
    result = stats.mannwhitneyu(overnight, intraday, alternative="greater")
    return {"statistic": float(result.statistic), "p_value": float(result.pvalue)}


def bootstrap_mean_diff(
    df: pd.DataFrame,
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> dict[str, float]:
    pairs = df[["overnight_return", "intraday_return"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(pairs) < 2:
        return {
            "bootstrap_mean_diff": np.nan,
            "bootstrap_ci_low": np.nan,
            "bootstrap_ci_high": np.nan,
        }
    diffs = (pairs["overnight_return"] - pairs["intraday_return"]).to_numpy()
    rng = np.random.default_rng(seed)
    samples = rng.choice(diffs, size=(n_bootstrap, len(diffs)), replace=True).mean(axis=1)
    return {
        "bootstrap_mean_diff": float(diffs.mean()),
        "bootstrap_ci_low": float(np.percentile(samples, 2.5)),
        "bootstrap_ci_high": float(np.percentile(samples, 97.5)),
    }


def summarize_symbol(
    df: pd.DataFrame,
    trading_days: int = 252,
    n_bootstrap: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    if df.empty:
        return {}

    data = df.sort_values("date").copy()
    symbol = data["symbol"].iloc[0] if "symbol" in data.columns else "portfolio"
    market = data["market"].iloc[0] if "market" in data.columns else ""
    name = data["name"].iloc[0] if "name" in data.columns else symbol
    asset_type = data["asset_type"].iloc[0] if "asset_type" in data.columns else ""
    valid = data.dropna(subset=["overnight_return", "intraday_return", "close_to_close_return"])

    overnight_total = float(np.exp(_clean_returns(data["overnight_return"]).sum()) - 1)
    intraday_total = float(np.exp(_clean_returns(data["intraday_return"]).sum()) - 1)
    close_total = float(np.exp(_clean_returns(data["close_to_close_return"]).sum()) - 1)

    ttest = welch_ttest_overnight_vs_intraday(data)
    bootstrap = bootstrap_mean_diff(data, n_bootstrap=n_bootstrap, seed=seed)
    mann_whitney = mann_whitney_overnight_vs_intraday(data)

    summary: dict[str, Any] = {
        "market": market,
        "symbol": symbol,
        "name": name,
        "asset_type": asset_type,
        "start_date": data["date"].min().strftime("%Y-%m-%d"),
        "end_date": data["date"].max().strftime("%Y-%m-%d"),
        "sample_trading_days": int(len(valid)),
        "overnight_annual_return": annualized_return(data["overnight_return"], trading_days),
        "intraday_annual_return": annualized_return(data["intraday_return"], trading_days),
        "close_to_close_annual_return": annualized_return(data["close_to_close_return"], trading_days),
        "overnight_annual_volatility": annualized_volatility(data["overnight_return"], trading_days),
        "intraday_annual_volatility": annualized_volatility(data["intraday_return"], trading_days),
        "overnight_sharpe": sharpe_ratio(data["overnight_return"], trading_days=trading_days),
        "intraday_sharpe": sharpe_ratio(data["intraday_return"], trading_days=trading_days),
        "overnight_win_rate": win_rate(data["overnight_return"]),
        "intraday_win_rate": win_rate(data["intraday_return"]),
        "overnight_mean": float(_clean_returns(data["overnight_return"]).mean()),
        "intraday_mean": float(_clean_returns(data["intraday_return"]).mean()),
        "mean_diff": float(_clean_returns(data["overnight_return"]).mean() - _clean_returns(data["intraday_return"]).mean()),
        "welch_t_statistic": ttest["statistic"],
        "p_value": ttest["p_value"],
        "mann_whitney_statistic": mann_whitney["statistic"],
        "mann_whitney_p_value": mann_whitney["p_value"],
        "max_drawdown": max_drawdown(data["close_to_close_cum_return"]),
        "overnight_total_return": overnight_total,
        "intraday_total_return": intraday_total,
        "close_to_close_total_return": close_total,
        "overnight_to_close_total_ratio": overnight_total / close_total if close_total else np.nan,
        "intraday_to_close_total_ratio": intraday_total / close_total if close_total else np.nan,
    }
    summary.update(bootstrap)
    return summary
