"""
Breakout strategy.

Rule: hold a stock when it closes at a new N-month high. The idea is
to catch the start of a new move, rather than confirming an established
trend (trend_following.py) or fading a dip (mean_reversion.py).
"""

import pandas as pd

from ..config import Config, DEFAULT_CONFIG


def calculate_rolling_high(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Rolling highest monthly close over config.breakout_lookback_months,
    excluding the current month - so "new high" means a genuine
    breakout above prior levels, not just a value compared to itself.
    """
    window = config.breakout_lookback_months
    return monthly_prices.shift(1).rolling(window).max()


def calculate_rolling_low(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Rolling lowest monthly close over config.breakout_lookback_months,
    excluding the current month. Mirror of calculate_rolling_high.
    """
    window = config.breakout_lookback_months
    return monthly_prices.shift(1).rolling(window).min()


def select_breakout_stocks(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Flag a stock as breaking out (long candidate) when its current
    price exceeds its prior rolling high.

    Returns a boolean DataFrame, same shape as monthly_prices.
    """
    rolling_high = calculate_rolling_high(monthly_prices, config)
    return monthly_prices > rolling_high


def select_breakdown_stocks(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Flag a stock as breaking down (short candidate) when its current
    price falls below its prior rolling low. Mirror of
    select_breakout_stocks.
    """
    rolling_low = calculate_rolling_low(monthly_prices, config)
    return monthly_prices < rolling_low


# Aliases so alpha/scanner.py can treat every strategy the same way:
# (monthly_prices, config) -> signal.
get_long_signal = select_breakout_stocks
get_short_signal = select_breakdown_stocks
