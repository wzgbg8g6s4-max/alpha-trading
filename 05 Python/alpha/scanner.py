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
    daily_prices: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Score every ticker by how many strategies flag it for a given
    month, sorted strongest first.

    Note this uses each strategy's signal AS OF that month directly -
    it is NOT shifted like a backtest position, because a scan is
    telling you what the strategies say right now, not simulating a
    trade you'd have already taken. Don't feed scanner output straight
    into build_portfolio()/run_backtest() without shifting it yourself.

    daily_prices is optional - pass the DAILY (not monthly) prices
    DataFrame from get_prices() to add last_close and price_date
    columns showing each ticker's most recent closing price. The
    scanner's signals are all computed on monthly-resampled prices, so
    this is deliberately a separate, optional input rather than
    something derived from monthly_prices, which wouldn't have a
    genuine "yesterday's close" in it.

    Returns a DataFrame with one row per ticker/direction that had at
    least one strategy flag it, columns: as_of, ticker, direction,
    score, strategies, conflicting_signal, and (if daily_prices was
    given) last_close, price_date. Empty DataFrame if nothing was
    flagged.
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

    if daily_prices is not None:
        opportunities = attach_latest_prices(opportunities, daily_prices)

    return opportunities


def attach_latest_prices(
    opportunities: pd.DataFrame,
    daily_prices: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add last_close and price_date columns to a scan result, using the
    most recent valid (non-NaN) daily price per ticker.

    Looked up per-ticker rather than just taking the last row of
    daily_prices, because different exchanges close on different
    holidays - e.g. a US ticker and a FTSE ticker in the same universe
    can genuinely have different "most recent" dates. Using
    .last_valid_index() per column handles that correctly instead of
    assuming every ticker's last row is equally current.
    """
    if opportunities.empty:
        return opportunities

    last_valid_dates = daily_prices.apply(lambda col: col.last_valid_index())
    last_closes = daily_prices.apply(lambda col: col.loc[col.last_valid_index()] if col.last_valid_index() is not None else None)

    opportunities = opportunities.copy()
    opportunities["last_close"] = opportunities["ticker"].map(last_closes)
    opportunities["price_date"] = opportunities["ticker"].map(last_valid_dates)
    return opportunities


def scan_latest(
    monthly_prices: pd.DataFrame,
    regime: Optional[pd.Series] = None,
    config: Config = DEFAULT_CONFIG,
    registry: List[Tuple[str, Callable, Callable]] = STRATEGY_REGISTRY,
    daily_prices: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Convenience wrapper: scan_as_of() using the most recent month
    available in monthly_prices. Pass daily_prices (from get_prices())
    to include last_close / price_date columns - see scan_as_of() for
    details.
    """
    return scan_as_of(monthly_prices, monthly_prices.index[-1], regime, config, registry, daily_prices)


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
