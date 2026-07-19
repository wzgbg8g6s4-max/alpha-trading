"""
Dashboard data layer.

Pure functions, no Streamlit dependency - same "research vs.
implementation" split Sprint 3 established elsewhere in this package.
dashboard.py at the repo root imports these and renders them; this
module can be tested and reused without a running Streamlit app.
"""

from typing import Dict, Tuple

import pandas as pd

from .config import Config, DEFAULT_CONFIG
from .data import get_prices, get_monthly_prices, get_benchmark_prices
from .portfolio import calculate_monthly_returns
from .regime import calculate_regime
from .backtest import run_backtest, BacktestResult
from .analytics import summarize_performance
from .scanner import scan_latest
from .strategies import momentum, trend_following, mean_reversion, breakout


# Same idea as scanner.STRATEGY_REGISTRY - one place to add a strategy
# and have it show up everywhere that iterates over "all strategies".
STRATEGY_SIGNALS: Dict[str, Tuple] = {
    "Momentum": (momentum.get_long_signal, momentum.get_short_signal),
    "Trend Following": (trend_following.get_long_signal, trend_following.get_short_signal),
    "Mean Reversion": (mean_reversion.get_long_signal, mean_reversion.get_short_signal),
    "Breakout": (breakout.get_long_signal, breakout.get_short_signal),
}


def load_market_data(config: Config = DEFAULT_CONFIG) -> Dict:
    """
    Download prices, monthly prices, monthly returns, and the regime
    flag - everything the dashboard needs, in one call so it can sit
    behind a single cache entry instead of several.
    """
    prices = get_prices(config)
    monthly_prices = get_monthly_prices(prices)
    monthly_returns = calculate_monthly_returns(monthly_prices)

    benchmark_prices = get_benchmark_prices(config)
    monthly_benchmark = benchmark_prices.resample("ME").last()
    regime = calculate_regime(monthly_benchmark, config)

    return {
        "monthly_prices": monthly_prices,
        "monthly_returns": monthly_returns,
        "regime": regime,
    }


def run_all_strategies(
    market_data: Dict,
    config: Config = DEFAULT_CONFIG,
) -> Dict[str, BacktestResult]:
    """
    Run every strategy in STRATEGY_SIGNALS through the backtest engine
    against the given market data. Returns one BacktestResult per
    strategy name.
    """
    monthly_prices = market_data["monthly_prices"]
    monthly_returns = market_data["monthly_returns"]
    regime = market_data["regime"]

    results = {}
    for name, (long_fn, short_fn) in STRATEGY_SIGNALS.items():
        long_signal = long_fn(monthly_prices, config)
        short_signal = short_fn(monthly_prices, config)
        results[name] = run_backtest(
            monthly_returns, long_signal, short_signal, regime, config
        )

    return results


def build_performance_table(
    results: Dict[str, BacktestResult],
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> pd.DataFrame:
    """
    One row per strategy, built from summarize_performance() (Sprint 6).
    """
    rows = {}
    for name, result in results.items():
        summary = summarize_performance(result, monthly_prices, config)
        rows[name] = {
            "CAGR": summary.cagr,
            "Max Drawdown": summary.max_drawdown,
            "Sharpe": summary.sharpe_ratio,
            "Sortino": summary.sortino_ratio,
            "Profit Factor": summary.profit_factor,
            "Expectancy": summary.expectancy,
            "Win Rate": summary.win_rate,
            "Annualized Turnover": summary.annualized_turnover,
            "Num Trades": summary.num_trades,
        }

    return pd.DataFrame(rows).T


def build_growth_table(results: Dict[str, BacktestResult]) -> pd.DataFrame:
    """
    One column per strategy's growth series, aligned by date - ready
    to hand straight to a line chart.
    """
    return pd.DataFrame({name: result.growth for name, result in results.items()})


def get_current_scan(market_data: Dict, config: Config = DEFAULT_CONFIG) -> pd.DataFrame:
    """
    Thin wrapper around scanner.scan_latest() using already-loaded
    market data, so the dashboard doesn't re-download anything.
    """
    return scan_latest(market_data["monthly_prices"], market_data["regime"], config)
