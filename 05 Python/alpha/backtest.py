"""
Backtesting engine.

Everything up to Sprint 4 ran a strategy once over full history with
zero costs - fine for checking the logic works, not good enough to
tell you whether a strategy is actually worth trading. This module
adds two things:

1. Transaction costs and slippage, deducted from returns based on
   actual monthly turnover, not a flat guess.
2. Signal shifting happens INSIDE this module now, not in notebooks.
   Every earlier notebook had a manual ".shift(1)" scattered through
   it - easy to forget, and forgetting it silently creates a
   look-ahead bug (trading on information you wouldn't have had yet).
   run_backtest() takes the raw, unshifted signal and shifts it itself,
   so that mistake isn't possible from here on.

There's also a walk-forward utility. None of the current strategies
fit parameters on a training window (their lookbacks are fixed in
Config), so today walk-forward mainly answers "is this strategy's
performance concentrated in one lucky stretch, or does it hold up
across different periods of history". It becomes more directly useful
once any kind of parameter selection gets added.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import Config, DEFAULT_CONFIG
from .regime import apply_regime_filter


@dataclass
class BacktestResult:
    returns: pd.Series
    growth: pd.Series
    turnover: pd.Series
    transaction_costs: pd.Series
    avg_holdings: float
    long_positions: pd.DataFrame
    short_positions: Optional[pd.DataFrame] = None

    @property
    def total_cost_drag(self) -> float:
        """Cumulative return given up to transaction costs and slippage."""
        return self.transaction_costs.sum()

    @property
    def final_growth(self) -> float:
        return self.growth.iloc[-1] if len(self.growth) else float("nan")


def calculate_weights(positions: pd.DataFrame) -> pd.DataFrame:
    """
    Equal weight across whatever's held each period. Months with zero
    holdings get zero weight everywhere rather than dividing by zero.

    holdings_count is explicitly floated and zeros replaced with NaN
    before dividing - on small universes pandas quietly produces NaN
    for a 0/0 anyway, but on larger ones (tested with ~90 tickers)
    pandas can switch to a different internal engine that raises a
    real ZeroDivisionError instead. Doing the replacement explicitly
    avoids depending on which engine pandas happens to pick.
    """
    holdings_count = positions.sum(axis=1).astype(float).replace(0, np.nan)
    weights = positions.div(holdings_count, axis=0)
    return weights.fillna(0.0)


def calculate_turnover(weights: pd.DataFrame) -> pd.Series:
    """
    One-way turnover per period - half the sum of absolute weight
    changes, so buying and selling the same amount in the same month
    doesn't get double counted.
    """
    weight_changes = weights.fillna(0.0).diff().abs().sum(axis=1)
    return (weight_changes / 2).fillna(0.0)


def apply_transaction_costs(
    turnover: pd.Series,
    config: Config = DEFAULT_CONFIG,
) -> pd.Series:
    """
    Cost drag per period, in return terms: turnover * (cost + slippage).
    """
    cost_rate = (config.transaction_cost_bps + config.slippage_bps) / 10_000
    return turnover * cost_rate


def run_backtest(
    monthly_returns: pd.DataFrame,
    long_signal: pd.DataFrame,
    short_signal: Optional[pd.DataFrame] = None,
    regime: Optional[pd.Series] = None,
    config: Config = DEFAULT_CONFIG,
) -> BacktestResult:
    """
    Run a full backtest for one strategy.

    long_signal / short_signal must be the RAW, unshifted boolean
    signal straight out of alpha/strategies/ - this function shifts by
    one period internally. Do not pre-shift before calling this;
    that's the whole point of centralising it here.

    Deducts transaction costs and slippage based on actual turnover.
    If short_signal is None, this is a long-only backtest.
    """
    long_positions = long_signal.shift(1)

    if regime is not None:
        long_positions = apply_regime_filter(long_positions, regime, direction="long")

    long_weights = calculate_weights(long_positions)

    if short_signal is not None:
        short_positions = short_signal.shift(1)
        if regime is not None:
            short_positions = apply_regime_filter(short_positions, regime, direction="short")
        short_weights = -calculate_weights(short_positions)

        # Equal split of capital between long and short legs - a
        # simplification, same caveat as build_long_short_portfolio.
        weights = (long_weights + short_weights) / 2
        avg_holdings = (
            long_positions.sum(axis=1) + short_positions.sum(axis=1)
        ).mean()
    else:
        short_positions = None
        weights = long_weights
        avg_holdings = long_positions.sum(axis=1).mean()

    gross_returns = (monthly_returns * weights).sum(axis=1)

    turnover = calculate_turnover(weights)
    costs = apply_transaction_costs(turnover, config)

    net_returns = gross_returns - costs
    growth = (1 + net_returns.fillna(0)).cumprod()

    return BacktestResult(
        returns=net_returns,
        growth=growth,
        turnover=turnover,
        transaction_costs=costs,
        avg_holdings=avg_holdings,
        long_positions=long_positions,
        short_positions=short_positions,
    )


def generate_walk_forward_windows(
    monthly_index: pd.DatetimeIndex,
    train_months: int = 36,
    test_months: int = 12,
    step_months: int = 12,
) -> List[Tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
    """
    Split a monthly index into rolling (train, test) window pairs.

    The train window isn't used for anything yet since nothing fits
    parameters on it - it's returned anyway so it's ready for when
    Sprint 6+ adds parameter selection, without changing this function.
    """
    windows = []
    start = 0

    while start + train_months + test_months <= len(monthly_index):
        train_index = monthly_index[start : start + train_months]
        test_index = monthly_index[
            start + train_months : start + train_months + test_months
        ]
        windows.append((train_index, test_index))
        start += step_months

    return windows


def run_walk_forward_backtest(
    monthly_returns: pd.DataFrame,
    long_signal: pd.DataFrame,
    short_signal: Optional[pd.DataFrame] = None,
    regime: Optional[pd.Series] = None,
    config: Config = DEFAULT_CONFIG,
    train_months: int = 36,
    test_months: int = 12,
    step_months: int = 12,
) -> pd.DataFrame:
    """
    Run run_backtest() on each out-of-sample test window and summarise
    the results - one row per window, showing whether performance is
    consistent across different stretches of history or concentrated
    in one lucky period.

    Note: each test window is backtested independently, so the very
    first month of each window loses its position (nothing to shift
    from the prior month once sliced). Minor edge effect, doesn't
    affect the comparison across windows.
    """
    windows = generate_walk_forward_windows(
        monthly_returns.index, train_months, test_months, step_months
    )

    rows = []
    for train_index, test_index in windows:
        test_returns = monthly_returns.loc[test_index]
        test_long = long_signal.loc[test_index]
        test_short = short_signal.loc[test_index] if short_signal is not None else None
        test_regime = regime.loc[test_index] if regime is not None else None

        result = run_backtest(
            test_returns, test_long, test_short, test_regime, config
        )

        rows.append({
            "test_start": test_index[0],
            "test_end": test_index[-1],
            "final_growth": result.final_growth,
            "avg_turnover": result.turnover.mean(),
            "avg_holdings": result.avg_holdings,
        })

    return pd.DataFrame(rows)
