"""
Trade journal.

Paper trading only teaches you something if you can look back and
compare decisions against outcomes. This is a plain CSV journal - one
row per trade, appended when you open a paper trade, updated when you
close it. Deliberately simple: no database, just a file you (or this
code) can read.

Closed trades store a "return" column in the same shape as the trade
logs built by alpha/analytics.py's build_trade_log(), so
summarize_journal() below reuses calculate_win_rate(),
calculate_profit_factor(), and calculate_expectancy() directly instead
of re-implementing the same math for real trades vs. backtested ones.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from .analytics import calculate_win_rate, calculate_profit_factor, calculate_expectancy

JOURNAL_COLUMNS = [
    "trade_id", "date_opened", "ticker", "direction", "strategy",
    "entry_price", "stop_loss", "shares", "risk_amount", "account_size",
    "notes", "date_closed", "exit_price", "return", "status",
]


def initialize_journal(path: str) -> None:
    """
    Create an empty journal file with the right columns if one doesn't
    already exist. Safe to call every time - does nothing if the file
    is already there, so other functions can call it defensively.
    """
    file_path = Path(path)
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=JOURNAL_COLUMNS).to_csv(file_path, index=False)


def load_journal(path: str) -> pd.DataFrame:
    """
    Load the journal, creating an empty one first if it doesn't exist
    yet - so this is always safe to call even before any trade has
    been logged.

    Reads every column as plain string (dtype=str, keep_default_na=False).
    Without this, an all-empty column like date_closed (before any
    trade has closed) gets inferred as float64 on read, and pandas
    then refuses to write a date string into it later - only surfaces
    once you actually try to close a trade, so worth forcing string
    dtype up front rather than hitting that downstream.
    """
    initialize_journal(path)
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def log_trade_open(
    path: str,
    ticker: str,
    direction: str,
    strategy: str,
    entry_price: float,
    stop_loss: float,
    shares: int,
    account_size: float,
    notes: str = "",
    date_opened: Optional[str] = None,
) -> str:
    """
    Append a new open trade to the journal. Returns the trade_id so
    you can reference it later when closing the trade - hang onto it.
    """
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")

    journal = load_journal(path)

    trade_id = f"{ticker}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    risk_amount = abs(entry_price - stop_loss) * shares

    new_row = {
        "trade_id": trade_id,
        "date_opened": date_opened or date.today().isoformat(),
        "ticker": ticker,
        "direction": direction,
        "strategy": strategy,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "shares": shares,
        "risk_amount": risk_amount,
        "account_size": account_size,
        "notes": notes,
        "date_closed": "",
        "exit_price": "",
        "return": "",
        "status": "open",
    }

    journal = pd.concat([journal, pd.DataFrame([new_row])], ignore_index=True)
    journal.to_csv(path, index=False)

    return trade_id


def log_trade_close(
    path: str,
    trade_id: str,
    exit_price: float,
    date_closed: Optional[str] = None,
) -> pd.DataFrame:
    """
    Close an open trade by trade_id: records exit price, computes
    return (using the same long/short convention as
    analytics.build_trade_log), marks status as closed. Returns the
    updated journal.
    """
    journal = load_journal(path)

    matches = journal.index[journal["trade_id"] == trade_id]
    if len(matches) == 0:
        raise ValueError(f"No trade found with trade_id '{trade_id}'")

    row_index = matches[0]
    direction = journal.loc[row_index, "direction"]
    entry_price = float(journal.loc[row_index, "entry_price"])

    if direction == "long":
        trade_return = exit_price / entry_price - 1
    else:
        trade_return = entry_price / exit_price - 1

    journal.loc[row_index, "exit_price"] = str(exit_price)
    journal.loc[row_index, "date_closed"] = str(date_closed or date.today().isoformat())
    journal.loc[row_index, "return"] = str(trade_return)
    journal.loc[row_index, "status"] = "closed"

    journal.to_csv(path, index=False)

    return journal


def get_open_trades(path: str) -> pd.DataFrame:
    journal = load_journal(path)
    return journal[journal["status"] == "open"]


def get_closed_trades(path: str) -> pd.DataFrame:
    journal = load_journal(path)
    closed = journal[journal["status"] == "closed"].copy()
    if not closed.empty:
        closed["return"] = closed["return"].astype(float)
    return closed


def summarize_journal(path: str) -> Dict:
    """
    Quick stats on closed paper trades - reuses the same win rate /
    profit factor / expectancy functions from alpha/analytics.py used
    for backtests, since a closed trade here has the same shape
    (a "return" column) as a reconstructed backtest trade.
    """
    closed = get_closed_trades(path)
    open_trades = get_open_trades(path)

    return {
        "num_open": len(open_trades),
        "num_closed": len(closed),
        "win_rate": calculate_win_rate(closed),
        "profit_factor": calculate_profit_factor(closed),
        "expectancy": calculate_expectancy(closed),
    }
