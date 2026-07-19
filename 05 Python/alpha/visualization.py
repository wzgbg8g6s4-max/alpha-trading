"""
Plotting helpers.

Kept separate so strategy and portfolio code don't need matplotlib
imports, and so the plotting library can be swapped later (e.g. for
Sprint 8's dashboard) without touching anything upstream.
"""

import matplotlib.pyplot as plt
import pandas as pd


def plot_portfolio(
    portfolio_growth: pd.Series,
    title: str = "Alpha Momentum Strategy",
) -> None:
    """
    Plot cumulative portfolio growth.
    """
    portfolio_growth.plot(figsize=(12, 6))
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Portfolio Growth")
    plt.grid(True)
    plt.show()
