"""
Universe loading.

config.Config.universe works fine as a short hardcoded list for 10
tickers, but gets unwieldy for something like the FTSE 100. This
module lets you keep a ticker list in a plain text/CSV file instead -
edit the file, not the code, when you want to change what's monitored.
"""

from pathlib import Path
from typing import List


def load_universe(path: str) -> List[str]:
    """
    Load a list of tickers from a file, one ticker per line.

    Blank lines and lines starting with '#' are ignored, so you can
    keep comments/notes in the file. If the file is a two-column CSV
    (ticker,name) only the first column is used - so
    "HSBA.L,HSBC Holdings" and "HSBA.L" both work.
    """
    tickers = []
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Universe file not found: {path}. "
            f"Check the path is relative to wherever you're running from."
        )

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ticker = line.split(",")[0].strip()
            if ticker:
                tickers.append(ticker)

    return tickers
