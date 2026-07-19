"""
Market regime filter.

Every strategy in alpha/strategies/ decides which stocks to trade, but
none of them know whether the overall market is in an uptrend,
downtrend, or chopping sideways. That matters - momentum and trend
following in particular tend to get chewed up when the broader market
is falling, no matter how well-picked the individual names are.

Rule: only take long positions when the benchmark (default SPY) is
above its own moving average, and only take short positions when it's
below. This sits on top of the strategies, it doesn't replace them -
it vetoes trades that go against the prevailing market direction.
"""

import pandas as pd

from .config import Config, DEFAULT_CONFIG


def calculate_regime(
    monthly_benchmark_prices: pd.Series,
    config: Config = DEFAULT_CONFIG,
) -> pd.Series:
    """
    Bull/bear regime flag: True when the benchmark is trading above its
    own rolling moving average (config.regime_ma_months).
    """
    if isinstance(monthly_benchmark_prices, pd.DataFrame):
        # Defensive: a single-ticker download should be a Series, but
        # some yfinance versions return a one-column DataFrame instead.
        monthly_benchmark_prices = monthly_benchmark_prices.iloc[:, 0]

    moving_average = monthly_benchmark_prices.rolling(config.regime_ma_months).mean()
    return monthly_benchmark_prices > moving_average


def apply_regime_filter(
    positions: pd.DataFrame,
    regime: pd.Series,
    direction: str = "long",
) -> pd.DataFrame:
    """
    Veto positions that go against the current regime.

    direction="long"  -> only keep positions in months the regime is bullish
    direction="short" -> only keep positions in months the regime is bearish

    positions and regime should share the same monthly DatetimeIndex.
    """
    if direction == "long":
        gate = regime
    elif direction == "short":
        gate = ~regime
    else:
        raise ValueError("direction must be 'long' or 'short'")

    gate = gate.reindex(positions.index).fillna(False)
    return positions.mul(gate, axis=0).astype(bool)
