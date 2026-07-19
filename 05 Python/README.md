# Alpha — Sprint 3: Research Framework

Refactor of the Sprint 2 momentum notebook into a reusable package.
Same logic as before, just organised so it can be imported instead of
copy-pasted, and so Sprint 4's new strategies (trend following, mean
reversion, breakout) can plug into the same data/portfolio code.

## Layout

```
alpha/
    config.py               # all settings live here, nothing hardcoded elsewhere
    data.py                 # download + reshape prices, nothing else
    portfolio.py            # turn positions into returns/growth
    visualization.py        # plotting only
    strategies/
        momentum.py          # Sprint 2's logic, unchanged, just relocated

notebooks/
    Sprint03_Momentum_Package.ipynb   # thin - imports the package, runs the analysis
```

## Setup

```bash
pip install -e .
```

or, without installing as a package:

```bash
pip install -r requirements.txt
```

## Usage

```python
from alpha.config import DEFAULT_CONFIG
from alpha.data import get_prices, get_monthly_prices
from alpha.strategies.momentum import (
    calculate_daily_momentum,
    rank_latest_momentum,
    calculate_monthly_momentum,
    select_top_stocks,
)
from alpha.portfolio import calculate_monthly_returns, build_portfolio
from alpha.visualization import plot_portfolio

prices = get_prices()
daily_momentum = calculate_daily_momentum(prices)
latest_rank = rank_latest_momentum(daily_momentum)

monthly_prices = get_monthly_prices(prices)
monthly_momentum = calculate_monthly_momentum(monthly_prices)
positions = select_top_stocks(monthly_momentum).shift(1)
monthly_returns = calculate_monthly_returns(monthly_prices)

portfolio_returns, portfolio_growth = build_portfolio(monthly_returns, positions)
plot_portfolio(portfolio_growth)
```

To test with a different universe or date range without touching any
function, pass a custom `Config`:

```python
from alpha.config import Config
from alpha.data import get_prices

test_config = Config(universe=["AAPL", "MSFT"], start_date="2023-01-01")
prices = get_prices(test_config)
```

## What changed from Sprint 2

- Constants (`START_DATE`, `UNIVERSE`, etc.) moved into a `Config`
  dataclass instead of module-level globals — you can now run the same
  code against different settings without editing it.
- Functions split by responsibility: data download, strategy signals,
  portfolio construction, and plotting are now four separate modules
  instead of one notebook cell block. Each can be tested and reused on
  its own.
- The notebook is now a thin runner — it imports from `alpha` and
  calls functions, it doesn't define them. That's the "research vs.
  implementation" split Sprint 3 asks for.

## Sprint 4 — Strategy Library

Three new strategies, same pattern as momentum: pure functions, take
a `Config`, return a boolean "hold this stock" DataFrame, feed straight
into `alpha/portfolio.py`. None of Sprint 3's code needed to change.

- `alpha/strategies/trend_following.py` — hold a stock while its price
  is above its own rolling moving average
- `alpha/strategies/mean_reversion.py` — hold stocks trading well below
  their recent average (z-score based), betting on a snap-back
- `alpha/strategies/breakout.py` — hold a stock when it closes at a new
  N-month high

`notebooks/Sprint04_Strategy_Library.ipynb` runs all four through the
same data and portfolio code and plots them together.

**One thing worth knowing before Sprint 10:** momentum ranks stocks
against each other and always holds a fixed top N. The other three are
per-stock filters — they can end up holding anywhere from zero to all
ten stocks in a given month. That's fine for research, but it means
equal-weighting them right now isn't quite the same as a properly
risk-managed portfolio. Sprint 10 (Portfolio Management) is where
position sizing and portfolio-level risk get handled properly — worth
revisiting these strategies against the 1%-per-trade rule at that
point.

## Sprint 4b — Regime Filter and Short-Side Mirrors

Two additions on top of the strategy library:

**`alpha/regime.py`** — gates every strategy's positions by the overall
market's direction. Longs are only allowed when the benchmark (default
SPY) is above its own moving average; shorts only when it's below.
Doesn't replace any strategy, sits on top of them.

**Short-side mirrors** — every strategy now has a long function and a
short function, same file, same pattern:

| Strategy | Long | Short |
|---|---|---|
| Momentum | `select_top_stocks` | `select_bottom_stocks` |
| Trend Following | `select_trend_positions` | `select_downtrend_positions` |
| Mean Reversion | `select_oversold_stocks` | `select_overbought_stocks` |
| Breakout | `select_breakout_stocks` | `select_breakdown_stocks` |

**`alpha/portfolio.py`** gained `build_long_short_portfolio`, which
correctly inverts the short leg's returns (you profit when a shorted
stock falls) and blends both legs assuming an equal capital split.
That equal-split assumption is a placeholder — real sizing per your
1%-per-trade rule is Sprint 10's job, not this function's.

`notebooks/Sprint04b_Regime_And_Shorts.ipynb` runs all four strategies
both ways — long-only (Sprint 4 baseline) and regime-gated long/short —
and plots them side by side.

## Sprint 5 — Backtesting Engine

**`alpha/backtest.py`** — new module, this is the core of the sprint.

- `run_backtest()` takes a strategy's **raw, unshifted** signal and
  shifts it internally. Every earlier notebook had a manual
  `.shift(1)` scattered through it — easy to forget, and forgetting it
  silently creates a look-ahead bug. From here on, shifting happens in
  one place, not wherever a notebook happens to remember to do it.
- Transaction costs and slippage are deducted based on **actual
  monthly turnover** (`transaction_cost_bps` + `slippage_bps` in
  `Config`), not a flat guess. `BacktestResult.total_cost_drag` tells
  you exactly how much return got eaten by trading.
- `run_walk_forward_backtest()` splits history into rolling
  train/test windows and reports each window's result separately, so
  a strategy that only worked because of one lucky year stands out
  instead of hiding inside a single full-history number.

`notebooks/Sprint05_Backtesting_Engine.ipynb` runs all four strategies
through the engine, shows gross vs. net-of-cost growth side by side,
and walks each one through rolling windows.

**Worth knowing:** the walk-forward split doesn't fit any parameters
on the train window yet, because none of the current strategies have
free parameters to fit — it's there mainly as a consistency check for
now, and becomes more directly useful once anything gets optimized.

## Sprint 6 — Performance Analytics

**`alpha/analytics.py`** — new module. Two kinds of stats:

- **From the returns series directly:** `calculate_cagr`,
  `calculate_max_drawdown`, `calculate_sharpe_ratio`,
  `calculate_sortino_ratio`, `calculate_annualized_turnover`.
- **From a reconstructed trade log:** `build_trade_log` walks a
  strategy's actual held positions (`BacktestResult.long_positions` /
  `.short_positions`) and turns entry/exit transitions into individual
  round-trip trades. That's what makes `calculate_win_rate`,
  `calculate_profit_factor`, and `calculate_expectancy` meaningful —
  they're computed on real trades, not approximated from monthly
  returns.

`summarize_performance()` runs all of it and returns one
`PerformanceSummary` per strategy. `notebooks/Sprint06_Performance_Analytics.ipynb`
builds a full comparison table across all four strategies plus a
drawdown chart, which is the number that tends to matter most for
whether you can actually stick with a strategy through a rough stretch.

**Worth setting deliberately:** `config.risk_free_rate` defaults to
0.0. Sharpe and Sortino are still directionally useful at that
setting, but set it to something like a current T-bill yield if you
want the numbers to mean something precise.

## Bugfix (post-Sprint 6)

`get_benchmark_prices()` and `calculate_regime()` now force the
benchmark price series to a plain `pd.Series` regardless of what shape
yfinance returns for a single ticker. Some yfinance versions return a
one-column DataFrame keyed by the ticker instead of a Series - left
unhandled, that turned `regime` into a DataFrame, which caused pandas
to align by column name during regime filtering and silently added a
spurious `'SPY'` column to the positions DataFrame. That surfaced as a
`KeyError: 'SPY'` in `build_trade_log`, several layers away from the
actual cause. Fixed at the source in `data.py`, with a defensive check
in `regime.py` too.

## Sprint 7 — Scanning Engine

**`alpha/scanner.py`** — new module. `scan_latest()` runs all four
strategies (long and short) against the current universe, gates by
the regime filter, and returns one ranked table: every ticker at
least one strategy currently flags, scored by how many strategies
agree, sorted strongest first.

- A stock flagged by three strategies at once outranks one flagged by
  a single strategy — that's the actual payoff of having a strategy
  library instead of just momentum alone.
- `flag_conflicts()` marks tickers where strategies disagree on
  direction (e.g. momentum says long, mean reversion says short
  because it's overbought). These get surfaced, not silently averaged
  away — worth a manual look rather than trusting the score alone.
- `top_opportunities(scan, n=3)` gives a shortlist sized to however
  many trades you're actually planning to manage that period.
- Adding a fifth strategy later means adding one line to
  `STRATEGY_REGISTRY` — every strategy module now exposes a uniform
  `get_long_signal(monthly_prices, config)` / `get_short_signal(...)`
  interface for exactly this reason.

**Important distinction, called out in the code and notebook:** scanner
output is *not* shifted the way a backtest position is. It's telling
you what the strategies say as of the latest month, not simulating a
trade already taken — don't feed it straight into `run_backtest()`
without shifting it yourself first.

`config.risk_per_trade` (1%, matching what you told me early on) is
defined now but not yet used to size anything — the scanner ranks,
it doesn't size. That's still Sprint 10's job.

`notebooks/Sprint07_Scanning_Engine.ipynb` runs the current scan,
shows the regime, and prints a shortlist plus any conflicting signals.

## Sprint 8 — Dashboard

**`dashboard.py`** (repo root) — a Streamlit app. Run it with:

```bash
streamlit run dashboard.py
```

Opens in your browser at `http://localhost:8501`. Three tabs:

- **This Week's Scan** — the Sprint 7 ranked opportunities table,
  a shortlist sized to however many trades you say you're managing,
  and any conflicting signals flagged separately
- **Performance** — the Sprint 6 comparison table (CAGR, Sharpe,
  Sortino, drawdown, profit factor, etc.) across all four strategies,
  plus a growth chart
- **Strategy Detail** — pick one strategy, see its growth curve,
  turnover, final growth, and cost drag on their own

Sidebar sliders (top stocks, lookback, transaction costs, slippage,
risk per trade) rebuild the `Config` live — move one and every tab
reruns against the new settings.

**Split the same way as everything else in this package:**
`alpha/dashboard_data.py` holds all the actual logic (no Streamlit
import anywhere in it) and can be tested on its own; `dashboard.py` is
UI wiring only. If you ever want a different frontend later, only
`dashboard.py` would need to change.

Market data is cached for an hour (`st.cache_data(ttl=3600)`) so
moving a slider doesn't trigger a fresh Yahoo Finance download every
time — only the parts that actually depend on the changed setting
rerun.

## Expanding the universe (e.g. to FTSE 100)

**`alpha/universes.py`** — `load_universe(path)` reads a ticker list
from a plain text/CSV file instead of needing to hardcode a Python
list in `config.py`. Edit the file to change what's monitored, no code
changes needed.

**`universes/ftse100.csv`** — a starting-point FTSE 100 ticker list
(Yahoo Finance `.L` suffix format). **Read the comment header in that
file before using it** — FTSE Russell reviews constituents quarterly,
this list was built from training data with a cutoff, and it's ~89
names rather than the full 100 (left incomplete deliberately rather
than guessing at ones I wasn't confident about). Verify it against
londonstockexchange.com or FTSE Russell's factsheet before relying on
it for anything real, then just edit the CSV directly.

`notebooks/Sprint08b_FTSE100_Universe.ipynb` shows the full pattern:
load the file, build a `Config` with the new universe, remember to
also change `regime_benchmark` to `"^FTSE"` (SPY tracks the S&P 500,
not relevant here), and bump `top_stocks` up from the default 3 -
holding only 3 out of 90 names is a much more concentrated bet than
holding 3 out of 10.

**Currency note:** every calculation in this package works on
percentage returns, so mixing currencies doesn't break the math - but
if you ever combine US and UK tickers in one universe, you're
implicitly taking on GBP/USD exchange rate risk that nothing here
currently adjusts for. Running FTSE 100 on its own sidesteps this.

**Bug found and fixed while testing this:** `calculate_weights()` in
`alpha/backtest.py` could raise a `ZeroDivisionError` on months with
zero holdings - but only on larger universes (~90+ tickers), because
pandas switches to a different internal calculation engine above a
certain size threshold that handles zero-division differently than it
does for small DataFrames. Never showed up with the original 10-stock
universe. Fixed by explicitly replacing zero holding-counts with NaN
before dividing, rather than relying on pandas' default behavior.

**Not yet done:** the dashboard's sidebar still only knows about the
original hardcoded universe - swapping `dashboard.py` to load from a
universe file too is a small follow-up, not built yet.

## Next: Sprint 9

Paper Trading — a daily decision process without risking money. This
is where the scanner's output turns into an actual routine you follow,
rather than something you only look at when you remember to.
