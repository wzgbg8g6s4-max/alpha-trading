"""
Configuration management.

Every strategy, backtest, and notebook should pull its settings from a
Config object rather than hardcoding constants. This is what lets the
same code run against different universes, date ranges, or lookback
windows without editing function bodies.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    start_date: str = "2020-01-01"
    end_date: str = "2025-01-01"

    lookback_days: int = 252
    lookback_months: int = 12

    top_stocks: int = 3

    # Trend following: how many months to average over for the trend filter
    trend_ma_months: int = 6

    # Mean reversion: lookback for the rolling mean/std, and how many
    # standard deviations away from average counts as oversold (long
    # candidate) or overbought (short candidate)
    mean_reversion_lookback_months: int = 3
    mean_reversion_z_threshold: float = -1.0
    mean_reversion_overbought_z_threshold: float = 1.0

    # Breakout: how many months back to look for the prior high/low
    breakout_lookback_months: int = 6

    # Regime filter: benchmark used to gauge overall market direction,
    # and the moving-average window that defines bull vs bear
    regime_benchmark: str = "SPY"
    regime_ma_months: int = 10

    # Backtesting: cost assumptions, in basis points, applied against
    # monthly turnover. Defaults are a rough retail-brokerage estimate,
    # not a promise - actual costs depend on your broker and how
    # liquid the names you trade are.
    transaction_cost_bps: float = 10.0
    slippage_bps: float = 5.0

    # Performance analytics: annual risk-free rate used in Sharpe/Sortino
    risk_free_rate: float = 0.0

    # Scanning/risk: your target risk per trade, as a fraction of
    # portfolio value.
    risk_per_trade: float = 0.01

    # Position sizing safety cap: no single position should exceed
    # this fraction of account value, regardless of what the risk
    # calculation alone would allow. Stops a very tight stop-loss from
    # sizing you into an oversized position.
    max_position_pct: float = 0.20

    universe: List[str] = field(default_factory=lambda: [
        "AAPL",
        "MSFT",
        "AMZN",
        "GOOGL",
        "META",
        "NVDA",
        "TSLA",
        "JPM",
        "V",
        "KO",
    ])


# Import this directly for the common case. Pass a different Config
# instance into any function below when you want to override settings
# (e.g. a smaller universe for a quick test run).
DEFAULT_CONFIG = Config()
