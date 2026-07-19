"""
Trend following strategy.

Rule: hold a stock only when its price is above its own longer-term
moving average. Unlike momentum, this doesn't rank stocks against each
other - it's a per-stock filter answering "is this stock in an uptrend
right now", which is closer to how a systematic trend follower actually
thinks about position management.

Note this means the number of stocks held can vary month to month -
anywhere from none to all of them - rather than always holding a fixed
top N like momentum does. Worth keeping in mind for position sizing
later (Sprint 10).
"""

import pandas as pd

from ..config import Config, DEFAULT_CONFIG


def calculate_moving_average(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Rolling moving average of monthly prices over config.trend_ma_months.
    """
    return monthly_prices.rolling(config.trend_ma_months).mean()


def select_trend_positions(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Flag a stock as "in trend" (long candidate) when its price is above
    its moving average.

    Returns a boolean DataFrame, same shape as monthly_prices.
    """
    moving_average = calculate_moving_average(monthly_prices, config)
    return monthly_prices > moving_average


def select_downtrend_positions(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Flag a stock as "in downtrend" (short candidate) when its price is
    below its moving average. Mirror of select_trend_positions.
    """
    moving_average = calculate_moving_average(monthly_prices, config)
    return monthly_prices < moving_average


# Aliases so alpha/scanner.py can treat every strategy the same way:
# (monthly_prices, config) -> signal.
get_long_signal = select_trend_positions
get_short_signal = select_downtrend_positions
