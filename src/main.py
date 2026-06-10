from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from src.backtest.portfolio import build_equal_weight_portfolio, summarize_portfolio
from src.backtest.returns import compute_cumulative_returns, compute_log_returns, validate_return_identity
from src.backtest.rolling import summarize_by_year, summarize_rolling_years
from src.backtest.statistics import summarize_symbol
from src.data_pipeline.cache import merge_incremental, next_start_date, read_cached_csv, write_cached_csv
from src.data_pipeline.normalize import normalize_ohlcv
from src.data_pipeline.validators import validate_ohlcv
from src.data_sources.baostock_client import BaoStockClient
from src.data_sources.twelve_data_client import TwelveDataClient
from src.report.charts import create_market_charts
from src.report.markdown_report import write_report
from src.utils.config_loader import load_config, load_symbols, resolve_path
from src.utils.logging import setup_logging

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Overnight/intraday return backtest and statistical report.")
    parser.add_argument("--market", choices=["all", "us", "cn"], default="all")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD. Defaults to config per market.")
    parser.add_argument("--end", default="today", help="End date YYYY-MM-DD or today.")
    parser.add_argument("--use-cache", action="store_true", help="Use local processed/raw cache without fetching.")
    parser.add_argument("--refresh", action="store_true", help="Ignore cache and refetch from start date.")
    parser.add_argument("--quick", action="store_true", help="Run a small recent sample for smoke tests.")
    parser.add_argument("--config", default="config/config.yaml")
    return parser.parse_args()


def normalize_end_date(end: str) -> str:
    if end.lower() == "today":
        return date.today().strftime("%Y-%m-%d")
    return pd.to_datetime(end).strftime("%Y-%m-%d")


def selected_markets(market_arg: str) -> list[str]:
    return ["us", "cn"] if market_arg == "all" else [market_arg]


def fetch_symbol_data(
    *,
    market: str,
    symbol: str,
    name: str,
    start: str,
    end: str,
    config: dict,
    existing_raw: pd.DataFrame,
    refresh: bool,
    us_client: TwelveDataClient | None,
    cn_client: BaoStockClient | None,
) -> pd.DataFrame:
    fetch_start = start if refresh else next_start_date(existing_raw, start)
    if pd.to_datetime(fetch_start) > pd.to_datetime(end):
        LOGGER.info("%s %s: cache already covers requested range", market.upper(), symbol)
        return pd.DataFrame()

    LOGGER.info("%s %s: fetching %s to %s", market.upper(), symbol, fetch_start, end)
    if market == "us":
        if us_client is None:
            raise RuntimeError("US client is not initialized")
        raw = us_client.fetch_daily(symbol, fetch_start, end)
        source = "twelve_data"
    else:
        if cn_client is None:
            raise RuntimeError("CN client is not initialized")
        raw = cn_client.fetch_daily(symbol, fetch_start, end)
        source = "baostock"

    return normalize_ohlcv(raw, market=market, symbol=symbol, name=name, source=source)


def process_market(
    market: str,
    *,
    args: argparse.Namespace,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    market_cfg = config["markets"][market]
    raw_dir = config["data"]["raw_dir"]
    processed_dir = config["data"]["processed_dir"]
    end = normalize_end_date(args.end)
    start = args.start or market_cfg["default_start"]

    if args.quick:
        raw_dir = "data/quick/raw"
        processed_dir = "data/quick/processed"
        end_ts = pd.to_datetime(end)
        start = max(
            pd.to_datetime(start),
            end_ts - pd.DateOffset(years=int(config["analysis"].get("quick_years", 3))),
        ).strftime("%Y-%m-%d")

    symbols = load_symbols(market)
    if args.quick:
        symbols = symbols.head(int(config["analysis"].get("quick_symbol_count", 3)))

    us_client = None
    cn_client = None
    if market == "us" and not args.use_cache:
        us_client = TwelveDataClient(
            request_interval_seconds=float(market_cfg.get("request_interval_seconds", 8)),
            minutely_limit=int(market_cfg.get("minutely_limit", 8)),
            rate_limit_safety_seconds=float(market_cfg.get("rate_limit_safety_seconds", 0.75)),
            max_retries=int(market_cfg.get("max_retries", 3)),
            retry_backoff_seconds=float(market_cfg.get("retry_backoff_seconds", 2)),
        )
    if market == "cn" and not args.use_cache:
        cn_client = BaoStockClient(adjustflag=str(market_cfg.get("adjustflag", "3")))

    processed_frames: list[pd.DataFrame] = []
    summary_rows: list[dict] = []
    validation_issues: list[str] = []
    trading_days = int(market_cfg.get("trading_days", 252))
    n_bootstrap = int(config["analysis"].get("bootstrap_samples", 10000))
    if args.quick:
        n_bootstrap = min(n_bootstrap, 1000)
    seed = int(config["analysis"].get("bootstrap_seed", 42))

    try:
        for row in symbols.itertuples(index=False):
            symbol = str(row.symbol)
            name = str(row.name)
            asset_type = str(row.asset_type)

            processed_cached = read_cached_csv(processed_dir, market, symbol)
            if args.use_cache and not processed_cached.empty:
                processed_cached["asset_type"] = processed_cached.get("asset_type", asset_type)
                processed_frames.append(processed_cached)
                summary_rows.append(summarize_symbol(processed_cached, trading_days, n_bootstrap, seed))
                continue

            existing_raw = pd.DataFrame() if args.refresh else read_cached_csv(raw_dir, market, symbol)
            incoming = pd.DataFrame()
            if not args.use_cache:
                incoming = fetch_symbol_data(
                    market=market,
                    symbol=symbol,
                    name=name,
                    start=start,
                    end=end,
                    config=config,
                    existing_raw=existing_raw,
                    refresh=args.refresh,
                    us_client=us_client,
                    cn_client=cn_client,
                )
            elif existing_raw.empty:
                LOGGER.warning("%s %s: no cache found, skipping", market.upper(), symbol)
                continue

            raw_merged = merge_incremental(existing_raw, incoming)
            if raw_merged.empty:
                LOGGER.warning("%s %s: no data after cache/fetch merge", market.upper(), symbol)
                continue
            write_cached_csv(raw_merged, raw_dir, market, symbol)

            validation = validate_ohlcv(raw_merged, symbol)
            validation_issues.extend(validation.issues)
            if validation.df.empty:
                LOGGER.warning("%s %s: no data after validation", market.upper(), symbol)
                continue

            returns = compute_log_returns(validation.df)
            returns = compute_cumulative_returns(returns)
            validate_return_identity(returns)
            returns["asset_type"] = asset_type
            write_cached_csv(returns, processed_dir, market, symbol)
            processed_frames.append(returns)
            summary_rows.append(summarize_symbol(returns, trading_days, n_bootstrap, seed))
    finally:
        if cn_client is not None:
            cn_client.close()

    market_data = pd.concat(processed_frames, ignore_index=True) if processed_frames else pd.DataFrame()
    summary = pd.DataFrame([row for row in summary_rows if row])
    portfolio_curve = build_equal_weight_portfolio(market_data, market) if not market_data.empty else pd.DataFrame()
    portfolio_summary = pd.DataFrame(
        [summarize_portfolio(market_data, market, trading_days, n_bootstrap, seed)]
    ).dropna(how="all")

    return market_data, summary, portfolio_curve, validation_issues


def write_outputs(
    *,
    config: dict,
    market_data: dict[str, pd.DataFrame],
    summaries: dict[str, pd.DataFrame],
    portfolio_curves: dict[str, pd.DataFrame],
    portfolio_summaries: dict[str, pd.DataFrame],
    validation_issues: list[str],
) -> None:
    output_dir = resolve_path(config["reports"]["output_dir"])
    figures_dir = resolve_path(config["reports"]["figures_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    for market, summary in summaries.items():
        summary.to_csv(output_dir / f"summary_{market}.csv", index=False)
    for market, summary in portfolio_summaries.items():
        summary.to_csv(output_dir / f"portfolio_summary_{market}.csv", index=False)

    combined_frames: list[pd.DataFrame] = []
    for market in market_data:
        if not market_data[market].empty:
            combined_frames.append(market_data[market])
        if not portfolio_curves[market].empty:
            combined_frames.append(portfolio_curves[market])
    combined = pd.concat(combined_frames, ignore_index=True) if combined_frames else pd.DataFrame()

    trading_days_by_market = {
        "us": int(config["markets"]["us"].get("trading_days", 252)),
        "cn": int(config["markets"]["cn"].get("trading_days", 244)),
    }
    rolling_bootstrap = min(int(config["analysis"].get("bootstrap_samples", 10000)), 2000)
    seed = int(config["analysis"].get("bootstrap_seed", 42))

    by_year = summarize_by_year(combined, trading_days_by_market, rolling_bootstrap, seed)
    rolling_3y = summarize_rolling_years(combined, 3, trading_days_by_market, rolling_bootstrap, seed)
    rolling_5y = summarize_rolling_years(combined, 5, trading_days_by_market, rolling_bootstrap, seed)

    by_year.to_csv(output_dir / "by_year_summary.csv", index=False)
    rolling_3y.to_csv(output_dir / "rolling_3y_summary.csv", index=False)
    rolling_5y.to_csv(output_dir / "rolling_5y_summary.csv", index=False)

    figures = create_market_charts(portfolio_curves, summaries, by_year, figures_dir)
    write_report(
        output_dir / "report.md",
        summaries=summaries,
        portfolio_summaries=portfolio_summaries,
        by_year_summary=by_year,
        rolling_3y_summary=rolling_3y,
        rolling_5y_summary=rolling_5y,
        figures=figures,
        config=config,
        validation_issues=validation_issues,
    )


def main() -> None:
    setup_logging()
    args = parse_args()
    config = load_config(args.config)

    market_data: dict[str, pd.DataFrame] = {}
    summaries: dict[str, pd.DataFrame] = {}
    portfolio_curves: dict[str, pd.DataFrame] = {}
    portfolio_summaries: dict[str, pd.DataFrame] = {}
    validation_issues: list[str] = []

    for market in selected_markets(args.market):
        LOGGER.info("Processing %s market", market.upper())
        data, summary, portfolio_curve, issues = process_market(market, args=args, config=config)
        market_data[market] = data
        summaries[market] = summary
        portfolio_curves[market] = portfolio_curve
        if not data.empty:
            trading_days = int(config["markets"][market].get("trading_days", 252))
            portfolio_summaries[market] = pd.DataFrame(
                [
                    summarize_portfolio(
                        data,
                        market,
                        trading_days,
                        min(int(config["analysis"].get("bootstrap_samples", 10000)), 1000 if args.quick else 10000),
                        int(config["analysis"].get("bootstrap_seed", 42)),
                    )
                ]
            ).dropna(how="all")
        else:
            portfolio_summaries[market] = pd.DataFrame()
        validation_issues.extend(issues)

    write_outputs(
        config=config,
        market_data=market_data,
        summaries=summaries,
        portfolio_curves=portfolio_curves,
        portfolio_summaries=portfolio_summaries,
        validation_issues=validation_issues,
    )
    LOGGER.info("Done. Reports written to %s", Path(config["reports"]["output_dir"]).as_posix())


if __name__ == "__main__":
    main()
