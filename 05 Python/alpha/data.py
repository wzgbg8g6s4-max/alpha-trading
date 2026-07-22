"""
Data access layer.

Handles downloading and reshaping price data. Nothing here should know
about strategies, positions, or portfolios - just prices in, prices out.
Keeping this boundary clean means you can swap the data source later
(a different vendor, a local cache, live feeds) without touching any
strategy code.
"""

import pandas as pd
import yfinance as yf

from .config import Config, DEFAULT_CONFIG


def get_prices(config: Config = DEFAULT_CONFIG) -> pd.DataFrame:
    """
    Download daily closing prices for the configured universe.

    config.end_date=None (the default) is passed straight through as
    end=None to yfinance, which is yfinance's own default meaning "no
    end limit, download up to today". Don't replace None with a
    computed date string here - that would just reintroduce a fixed
    cutoff at whatever moment this code happened to run.
    """
    prices = yf.download(
        config.universe,
        start=config.start_date,
        end=config.end_date,
    )["Close"]

    return prices


def get_benchmark_prices(config: Config = DEFAULT_CONFIG) -> pd.Series:
    """
    Download daily closing prices for the regime benchmark
    (config.regime_benchmark, e.g. "SPY") used by alpha/regime.py.

    Different yfinance versions return a single ticker's data
    differently - sometimes a plain Series, sometimes a one-column
    DataFrame keyed by the ticker. Squeeze it to a Series explicitly
    so downstream code (regime.py, analytics.py) never has to guess
    what it's dealing with.
    """
    benchmark_prices = yf.download(
        config.regime_benchmark,
        start=config.start_date,
        end=config.end_date,
    )["Close"]

    if isinstance(benchmark_prices, pd.DataFrame):
        benchmark_prices = benchmark_prices.iloc[:, 0]

    benchmark_prices.name = config.regime_benchmark

    return benchmark_prices


def get_monthly_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Convert daily prices into month-end prices.
    """
    return prices.resample("ME").last()
