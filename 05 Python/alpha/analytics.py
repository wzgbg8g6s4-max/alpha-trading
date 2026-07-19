"""
Performance analytics.

Sprint 5 gave us a growth chart per strategy. This module turns that
into actual comparable numbers: CAGR, max drawdown, Sharpe, Sortino,
turnover - plus, by reconstructing individual trades from the
positions a backtest actually held, real trade-level stats: win rate,
profit factor, and expectancy. Those three need a trade log, not just
a returns series, so they weren't possible before BacktestResult
started retaining its positions.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import pandas as pd

from .config import Config, DEFAULT_CONFIG
from .backtest import BacktestResult


def calculate_cagr(growth: pd.Series, periods_per_year: int = 12) -> float:
    """
    Compound annual growth rate from a growth-of-$1 series.
    """
    growth = growth.dropna()
    if len(growth) < 2 or growth.iloc[0] == 0:
        return float("nan")

    total_return = growth.iloc[-1] / growth.iloc[0]
    years = len(growth) / periods_per_year
    if years <= 0 or total_return <= 0:
        return float("nan")

    return total_return ** (1 / years) - 1


def calculate_max_drawdown(growth: pd.Series) -> Tuple[float, pd.Series]:
    """
    Maximum peak-to-trough decline. Returns (max_drawdown, drawdown_series);
    max_drawdown is negative - e.g. -0.25 means a 25% decline from the
    prior peak.
    """
    running_max = growth.cummax()
    drawdown = growth / running_max - 1
    return drawdown.min(), drawdown


def calculate_sharpe_ratio(
    returns: pd.Series,
    config: Config = DEFAULT_CONFIG,
    periods_per_year: int = 12,
) -> float:
    """
    Annualized Sharpe ratio: excess return over the risk-free rate,
    divided by return volatility. Higher is better; doesn't distinguish
    upside volatility from downside (see Sortino for that).
    """
    returns = returns.dropna()
    if len(returns) < 2:
        return float("nan")

    monthly_rf = (1 + config.risk_free_rate) ** (1 / periods_per_year) - 1
    excess_returns = returns - monthly_rf

    if excess_returns.std() == 0:
        return float("nan")

    return excess_returns.mean() / excess_returns.std() * (periods_per_year ** 0.5)


def calculate_sortino_ratio(
    returns: pd.Series,
    config: Config = DEFAULT_CONFIG,
    periods_per_year: int = 12,
) -> float:
    """
    Like Sharpe, but only penalizes downside volatility - a strategy
    with big upside months and a low Sharpe (because it's "volatile")
    can still show a strong Sortino, which is often the more honest
    read for a directional strategy.
    """
    returns = returns.dropna()
    if len(returns) < 2:
        return float("nan")

    monthly_rf = (1 + config.risk_free_rate) ** (1 / periods_per_year) - 1
    excess_returns = returns - monthly_rf
    downside_returns = excess_returns[excess_returns < 0]
    downside_std = downside_returns.std()

    if downside_std == 0 or pd.isna(downside_std):
        return float("nan")

    return excess_returns.mean() / downside_std * (periods_per_year ** 0.5)


def calculate_annualized_turnover(
    turnover: pd.Series,
    periods_per_year: int = 12,
) -> float:
    """
    Turnover annualized - roughly "how many times over the portfolio
    gets replaced per year". Worth checking this against how many
    trades/month you're actually comfortable managing.
    """
    return turnover.mean() * periods_per_year


def build_trade_log(
    positions: pd.DataFrame,
    monthly_prices: pd.DataFrame,
    side: str = "long",
) -> pd.DataFrame:
    """
    Reconstruct individual round-trip trades from a position matrix.

    positions should be the actual positions a backtest held -
    BacktestResult.long_positions or .short_positions, already shifted
    and already regime-gated. Uses monthly close prices as the entry/
    exit basis, consistent with the monthly-rebalanced portfolio used
    everywhere else in this package.

    side="long" or "short" determines how trade return is computed.
    Trades still open at the end of the data are excluded - there's no
    exit price to measure them against yet.
    """
    if side not in ("long", "short"):
        raise ValueError("side must be 'long' or 'short'")

    trades = []

    for ticker in positions.columns:
        held = positions[ticker].fillna(False)
        prices = monthly_prices[ticker]

        entry_date = None
        for date, is_held in held.items():
            if is_held and entry_date is None:
                entry_date = date
            elif not is_held and entry_date is not None:
                entry_price = prices.loc[entry_date]
                exit_price = prices.loc[date]

                if side == "long":
                    trade_return = exit_price / entry_price - 1
                else:
                    trade_return = entry_price / exit_price - 1

                trades.append({
                    "ticker": ticker,
                    "side": side,
                    "entry_date": entry_date,
                    "exit_date": date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return": trade_return,
                })
                entry_date = None
        # A trade still open at the end of the data has no exit price
        # yet - skipped rather than guessed at.

    return pd.DataFrame(trades)


def build_combined_trade_log(result: BacktestResult, monthly_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Build the trade log for both legs of a BacktestResult (long, and
    short if present) and combine them into one DataFrame.
    """
    trade_log = build_trade_log(result.long_positions, monthly_prices, side="long")

    if result.short_positions is not None:
        short_trades = build_trade_log(result.short_positions, monthly_prices, side="short")
        trade_log = pd.concat([trade_log, short_trades], ignore_index=True)

    return trade_log


def calculate_win_rate(trade_log: pd.DataFrame) -> float:
    """
    Fraction of trades that closed with a positive return.
    """
    if trade_log.empty:
        return float("nan")
    return (trade_log["return"] > 0).mean()


def calculate_profit_factor(trade_log: pd.DataFrame) -> float:
    """
    Gross profit from winning trades divided by gross loss from losing
    trades. Above 1 means winners outweigh losers in dollar terms;
    below 1 means the reverse, regardless of win rate - a strategy can
    win 80% of the time and still have a bad profit factor if the 20%
    of losses are large enough.
    """
    if trade_log.empty:
        return float("nan")

    gross_profit = trade_log.loc[trade_log["return"] > 0, "return"].sum()
    gross_loss = trade_log.loc[trade_log["return"] < 0, "return"].sum()

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else float("nan")

    return gross_profit / abs(gross_loss)


def calculate_expectancy(trade_log: pd.DataFrame) -> float:
    """
    Average return per trade. Positive expectancy means the strategy
    makes money per trade on average - this is computed on the same
    positions the backtest actually held, so cost/slippage effects on
    which trades get taken are already baked in, though the trade
    return itself doesn't separately deduct per-trade cost (that's
    already reflected in the backtest's net_returns series, at the
    portfolio level).
    """
    if trade_log.empty:
        return float("nan")
    return trade_log["return"].mean()


@dataclass
class PerformanceSummary:
    cagr: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    profit_factor: float
    expectancy: float
    win_rate: float
    annualized_turnover: float
    num_trades: int


def summarize_performance(
    result: BacktestResult,
    monthly_prices: pd.DataFrame,
    config: Config = DEFAULT_CONFIG,
) -> PerformanceSummary:
    """
    One-stop performance summary for a BacktestResult - the numbers
    that actually matter when comparing strategies against each other,
    rather than eyeballing growth charts.
    """
    max_dd, _ = calculate_max_drawdown(result.growth)
    trade_log = build_combined_trade_log(result, monthly_prices)

    return PerformanceSummary(
        cagr=calculate_cagr(result.growth),
        max_drawdown=max_dd,
        sharpe_ratio=calculate_sharpe_ratio(result.returns, config),
        sortino_ratio=calculate_sortino_ratio(result.returns, config),
        profit_factor=calculate_profit_factor(trade_log),
        expectancy=calculate_expectancy(trade_log),
        win_rate=calculate_win_rate(trade_log),
        annualized_turnover=calculate_annualized_turnover(result.turnover),
        num_trades=len(trade_log),
    )
