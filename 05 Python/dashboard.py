"""
Alpha Trading Research Platform - Dashboard

Run with:
    streamlit run dashboard.py

This file is UI wiring only - business logic lives in
alpha/dashboard_data.py, which has no Streamlit dependency and can be
tested on its own. Sidebar sliders rebuild a Config and everything
downstream (scan, backtests, performance table) reruns against it.
"""

import streamlit as st

from alpha.config import Config
from alpha.dashboard_data import (
    load_market_data,
    run_all_strategies,
    build_performance_table,
    build_growth_table,
    get_current_scan,
)
from alpha.scanner import top_opportunities

st.set_page_config(page_title="Alpha Research Dashboard", layout="wide")

st.title("Alpha Trading Research Platform")

# =====================================================
# SIDEBAR - SETTINGS
# =====================================================

st.sidebar.header("Settings")

top_stocks = st.sidebar.slider("Top stocks (momentum)", 1, 10, 3)
lookback_months = st.sidebar.slider("Momentum lookback (months)", 1, 24, 12)
transaction_cost_bps = st.sidebar.slider("Transaction cost (bps)", 0, 50, 10)
slippage_bps = st.sidebar.slider("Slippage (bps)", 0, 50, 5)
risk_per_trade_pct = st.sidebar.slider("Risk per trade (%)", 0.1, 5.0, 1.0, step=0.1)

config = Config(
    top_stocks=top_stocks,
    lookback_months=lookback_months,
    transaction_cost_bps=float(transaction_cost_bps),
    slippage_bps=float(slippage_bps),
    risk_per_trade=risk_per_trade_pct / 100,
)

st.sidebar.markdown("---")
st.sidebar.caption(f"Universe: {', '.join(config.universe)}")
st.sidebar.caption(f"Regime benchmark: {config.regime_benchmark}")


# =====================================================
# DATA
# =====================================================
# Cached so moving a slider doesn't trigger a fresh download every
# time - only the parts downstream of Config actually need to rerun.

@st.cache_data(ttl=3600, show_spinner=False)
def cached_market_data(_config: Config):
    return load_market_data(_config)


with st.spinner("Downloading market data..."):
    market_data = cached_market_data(config)

current_regime = "Bullish" if market_data["regime"].iloc[-1] else "Bearish"
regime_color = "green" if current_regime == "Bullish" else "red"
as_of = market_data["monthly_prices"].index[-1].date()

st.markdown(
    f"**Current regime:** :{regime_color}[{current_regime}]  |  **As of:** {as_of}"
)

# =====================================================
# TABS
# =====================================================

tab_scan, tab_performance, tab_detail = st.tabs(
    ["This Week's Scan", "Performance", "Strategy Detail"]
)

with tab_scan:
    st.subheader("Ranked Opportunities")
    scan = get_current_scan(market_data, config)

    if scan.empty:
        st.info("No opportunities flagged this month.")
    else:
        st.dataframe(scan, use_container_width=True)

        st.subheader("Shortlist")
        n = st.slider("How many trades are you managing this period?", 1, 10, 3)
        st.dataframe(top_opportunities(scan, n=n), use_container_width=True)

        conflicts = scan[scan["conflicting_signal"]]
        if not conflicts.empty:
            st.warning("Strategies disagree on direction for these tickers:")
            st.dataframe(conflicts, use_container_width=True)

with tab_performance:
    st.subheader("Strategy Comparison")

    with st.spinner("Running backtests..."):
        results = run_all_strategies(market_data, config)
        performance_table = build_performance_table(
            results, market_data["monthly_prices"], config
        )

    st.dataframe(
        performance_table.style.format({
            "CAGR": "{:.1%}",
            "Max Drawdown": "{:.1%}",
            "Sharpe": "{:.2f}",
            "Sortino": "{:.2f}",
            "Profit Factor": "{:.2f}",
            "Expectancy": "{:.2%}",
            "Win Rate": "{:.1%}",
            "Annualized Turnover": "{:.2f}",
            "Num Trades": "{:.0f}",
        }),
        use_container_width=True,
    )

    st.subheader("Growth Comparison")
    growth_table = build_growth_table(results)
    st.line_chart(growth_table)

with tab_detail:
    st.subheader("Strategy Detail")

    strategy_name = st.selectbox("Strategy", list(results.keys()))
    selected = results[strategy_name]

    col1, col2, col3 = st.columns(3)
    col1.metric("Final Growth", f"{selected.final_growth:.2f}x")
    col2.metric("Avg Holdings", f"{selected.avg_holdings:.1f}")
    col3.metric("Total Cost Drag", f"{selected.total_cost_drag:.2%}")

    st.line_chart(selected.growth.rename("Growth"))
    st.line_chart(selected.turnover.rename("Turnover"))
