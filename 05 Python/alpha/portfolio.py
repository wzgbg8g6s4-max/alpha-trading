"""
Portfolio construction.

Turns a strategy's position flags into actual portfolio returns and
growth. Deliberately strategy-agnostic - it doesn't care whether the
positions came from momentum, trend following, or anything else, so
Sprint 4's new strategies plug into this without changes.
"""

import pandas as pd
from typing import Tuple


def calculate_monthly_returns(monthly_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate monthly percentage returns.
    """
    return monthly_prices.pct_change()


def build_portfolio(
    monthly_returns: pd.DataFrame,
    positions: pd.DataFrame,
) -> Tuple[pd.Series, pd.Series]:
    """
    Build an equally weighted, long-only portfolio from position flags.

    positions should be a boolean DataFrame (True = hold), typically
    shifted by one period already so you're not trading on information
    you wouldn't have had at the time.

    Returns (portfolio_returns, portfolio_growth).
    """
    portfolio_returns = monthly_returns.where(positions).mean(axis=1)
    portfolio_growth = (1 + portfolio_returns.fillna(0)).cumprod()

    return portfolio_returns, portfolio_growth


def build_long_short_portfolio(
    monthly_returns: pd.DataFrame,
    long_positions: pd.DataFrame,
    short_positions: pd.DataFrame,
) -> Tuple[pd.Series, pd.Series]:
    """
    Build a portfolio that holds both a long leg and a short leg.

    A short position profits when the stock's price falls, so the
    short leg's return is the *negative* of the stock's return. The two
    legs are then blended assuming an equal split of capital between
    them (a simplification - real position sizing per your 1%-per-trade
    rule is Sprint 10's job, not this function's).

    Returns (portfolio_returns, portfolio_growth).
    """
    long_returns = monthly_returns.where(long_positions).mean(axis=1)
    short_returns = -monthly_returns.where(short_positions).mean(axis=1)

    combined_returns = pd.concat(
        [long_returns, short_returns], axis=1
    ).mean(axis=1)
    portfolio_growth = (1 + combined_returns.fillna(0)).cumprod()

    return combined_returns, portfolio_growth
