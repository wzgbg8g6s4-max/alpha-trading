"""
Mean reversion strategy.

Rule: hold stocks that have fallen furthest below their own recent
average, on the assumption that short-term dislocations tend to
correct. This is roughly the opposite bet to momentum/trend following,
which is exactly why it's useful to have both in the same library -
they tend to work in different market regimes.
"""

import pandas as pd

from ..config import Config, DEFAULT_CONFIG


def calculate_zscore(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Z-score of each month's price against its own rolling mean/std over
    config.mean_reversion_lookback_months. Negative values mean the
    price is below its recent average.
    """
    window = config.mean_reversion_lookback_months
    rolling_mean = monthly_prices.rolling(window).mean()
    rolling_std = monthly_prices.rolling(window).std()
    return (monthly_prices - rolling_mean) / rolling_std


def select_oversold_stocks(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Flag stocks trading meaningfully below their recent average
    (long candidates) - z-score below config.mean_reversion_z_threshold.

    Returns a boolean DataFrame, same shape as monthly_prices.
    """
    zscore = calculate_zscore(monthly_prices, config)
    return zscore < config.mean_reversion_z_threshold


def select_overbought_stocks(
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    Flag stocks trading meaningfully above their recent average
    (short candidates) - z-score above
    config.mean_reversion_overbought_z_threshold. Mirror of
    select_oversold_stocks.
    """
    zscore = calculate_zscore(monthly_prices, config)
    return zscore > config.mean_reversion_overbought_z_threshold


# Aliases so alpha/scanner.py can treat every strategy the same way:
# (monthly_prices, config) -> signal.
get_long_signal = select_oversold_stocks
get_short_signal = select_overbought_stocks
