"""
Momentum strategy.

Refactored out of Sprint02/03's notebook. Same logic, just organised so
it can be imported, tested, and reused instead of copy-pasted into every
new notebook.
"""

import pandas as pd

from ..config import Config, DEFAULT_CONFIG


def calculate_daily_momentum(
    prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Calculate momentum using daily prices over config.lookback_days.
    """
    return prices.pct_change(config.lookback_days)


def rank_latest_momentum(momentum: pd.DataFrame) -> pd.Series:
    """
    Rank the most recent momentum reading, strongest first.
    """
    return momentum.iloc[-1].sort_values(ascending=False)


def calculate_monthly_momentum(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Calculate momentum from monthly prices over config.lookback_months.
    """
    return monthly_prices.pct_change(config.lookback_months)


def select_top_stocks(
    monthly_momentum: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Flag the top N momentum stocks each month - long candidates.

    Returns a boolean DataFrame, same shape as monthly_momentum, where
    True means "hold this stock this month".
    """
    return (
        monthly_momentum
        .rank(axis=1, ascending=False)
        .apply(lambda x: x <= config.top_stocks)
    )


def select_bottom_stocks(
    monthly_momentum: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Flag the bottom N momentum stocks each month - short candidates.

    Mirror of select_top_stocks: weakest momentum instead of strongest.
    """
    return (
        monthly_momentum
        .rank(axis=1, ascending=True)
        .apply(lambda x: x <= config.top_stocks)
    )


def get_long_signal(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Full long signal straight from prices - momentum calculation and
    top-stock selection in one call. Exists so alpha/scanner.py can
    treat every strategy the same way: (monthly_prices, config) -> signal,
    without needing to know momentum has an extra step the other
    strategies don't.
    """
    monthly_momentum = calculate_monthly_momentum(monthly_prices, config)
    return select_top_stocks(monthly_momentum, config)


def get_short_signal(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Full short signal straight from prices. Mirror of get_long_signal.
    """
    monthly_momentum = calculate_monthly_momentum(monthly_prices, config)
    return select_bottom_stocks(monthly_momentum, config)
