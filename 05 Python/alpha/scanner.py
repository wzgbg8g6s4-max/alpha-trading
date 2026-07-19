"""
Scanning engine.

Sprint 4 gave us four strategies, each producing its own long/short
signal. Up to now, checking them meant running four notebooks and
eyeballing four separate outputs. This module turns that into one
ranked table: every ticker currently flagged by at least one strategy,
scored by how many strategies agree, gated by the regime filter,
sorted strongest first.

This doesn't replace the individual strategy notebooks - those are
still where you'd investigate why something's flagged. The scanner is
the "what should I actually look at this week" view sitting on top.
"""

from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from .config import Config, DEFAULT_CONFIG
from .regime import apply_regime_filter
from .strategies import momentum, trend_following, mean_reversion, breakout


# Each entry: (strategy_name, long_signal_function, short_signal_function).
# Every function takes (monthly_prices, config) and returns a boolean
# DataFrame - adding a new strategy to the scanner means adding one
# line here, nothing else in this file needs to change.
STRATEGY_REGISTRY: List[Tuple[str, Callable, Callable]] = [
    ("Momentum", momentum.get_long_signal, momentum.get_short_signal),
    ("Trend Following", trend_following.get_long_signal, trend_following.get_short_signal),
    ("Mean Reversion", mean_reversion.get_long_signal, mean_reversion.get_short_signal),
    ("Breakout", breakout.get_long_signal, breakout.get_short_signal),
]


def scan_as_of(
    monthly_prices: pd.DataFrame,
    as_of: pd.Timestamp,
    regime: Optional[pd.Series] = None,
    config: Config = DEFAULT_CONFIG,
    registry: List[Tuple[str, Callable, Callable]] = STRATEGY_REGISTRY,
) -> pd.DataFrame:
    """
    Score every ticker by how many strategies flag it for a given
    month, sorted strongest first.

    Note this uses each strategy's signal AS OF that month directly -
    it is NOT shifted like a backtest position, because a scan is
    telling you what the strategies say right now, not simulating a
    trade you'd have already taken. Don't feed scanner output straight
    into build_portfolio()/run_backtest() without shifting it yourself.

    Returns a DataFrame with one row per ticker/direction that had at
    least one strategy flag it, columns: as_of, ticker, direction,
    score, strategies, conflicting_signal. Empty DataFrame if nothing
    was flagged.
    """
    long_hits: Dict[str, List[str]] = {}
    short_hits: Dict[str, List[str]] = {}

    for name, long_fn, short_fn in registry:
        long_signal = long_fn(monthly_prices, config)
        short_signal = short_fn(monthly_prices, config)

        if regime is not None:
            long_signal = apply_regime_filter(long_signal, regime, direction="long")
            short_signal = apply_regime_filter(short_signal, regime, direction="short")

        if as_of not in long_signal.index:
            continue

        latest_long = long_signal.loc[as_of]
        latest_short = short_signal.loc[as_of]

        for ticker, flagged in latest_long.items():
            if flagged:
                long_hits.setdefault(ticker, []).append(name)

        for ticker, flagged in latest_short.items():
            if flagged:
                short_hits.setdefault(ticker, []).append(name)

    rows = []
    for ticker, strategies in long_hits.items():
        rows.append({
            "ticker": ticker,
            "direction": "long",
            "score": len(strategies),
            "strategies": ", ".join(strategies),
        })
    for ticker, strategies in short_hits.items():
        rows.append({
            "ticker": ticker,
            "direction": "short",
            "score": len(strategies),
            "strategies": ", ".join(strategies),
        })

    opportunities = pd.DataFrame(rows)
    if opportunities.empty:
        return opportunities

    opportunities = flag_conflicts(opportunities)
    opportunities = opportunities.sort_values(
        ["score", "ticker"], ascending=[False, True]
    ).reset_index(drop=True)
    opportunities.insert(0, "as_of", as_of)

    return opportunities


def scan_latest(
    monthly_prices: pd.DataFrame,
    regime: Optional[pd.Series] = None,
    config: Config = DEFAULT_CONFIG,
    registry: List[Tuple[str, Callable, Callable]] = STRATEGY_REGISTRY,
) -> pd.DataFrame:
    """
    Convenience wrapper: scan_as_of() using the most recent month
    available in monthly_prices.
    """
    return scan_as_of(monthly_prices, monthly_prices.index[-1], regime, config, registry)


def flag_conflicts(opportunities: pd.DataFrame) -> pd.DataFrame:
    """
    Mark tickers where different strategies disagree on direction -
    e.g. momentum says long, mean reversion says short (overbought at
    the same time momentum is strong). Worth a second look, not
    something to silently average away.
    """
    if opportunities.empty:
        return opportunities

    direction_counts = opportunities.groupby("ticker")["direction"].nunique()
    conflicting_tickers = set(direction_counts[direction_counts > 1].index)

    opportunities = opportunities.copy()
    opportunities["conflicting_signal"] = opportunities["ticker"].isin(conflicting_tickers)
    return opportunities


def top_opportunities(opportunities: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """
    First N rows of an already-sorted scan result - a shortlist sized
    to how many trades you're actually planning to manage this period.
    """
    return opportunities.head(n)
