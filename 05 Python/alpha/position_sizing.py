"""
Position sizing.

Deliberately lightweight - full portfolio management (sector exposure,
cash allocation across many simultaneous positions, correlation
between holdings) is a bigger job for later. Two ways to size a
position, both landing on the same underlying question - "how many
shares does my risk-per-trade rule actually allow":

- calculate_position_size(): sized against an actual stop-loss price.
  Matches how a discretionary trader typically thinks about risk.

- calculate_position_size_rebalance_only(): sized against an assumed
  maximum adverse move instead of a hard stop-loss order. This matches
  how the strategies in alpha/strategies/ were actually backtested -
  run_backtest() holds a position until the next monthly rebalance
  drops it, with no stop-loss logic anywhere in the backtest. If you
  paper trade with a real stop-loss, you're testing something the
  backtest never tested. This function lets you size a rebalance-only
  position using the same 1%-of-account discipline, without requiring
  an actual exit order.
"""

from dataclasses import dataclass

from .config import Config, DEFAULT_CONFIG


@dataclass
class PositionSize:
    shares: int
    risk_amount: float
    position_value: float
    position_pct_of_account: float
    risk_per_share: float
    capped_by_max_position: bool


def _size_from_risk_per_share(
    account_size: float,
    entry_price: float,
    risk_per_share: float,
    config: Config,
) -> PositionSize:
    """
    Shared sizing math for both stop-loss and rebalance-only sizing,
    once each has worked out what "risk per share" actually means for
    its situation. Keeps the risk-target and max-position-cap logic in
    one place rather than duplicated across both public functions.
    """
    risk_amount_target = account_size * config.risk_per_trade
    shares_from_risk = int(risk_amount_target // risk_per_share)

    max_position_value = account_size * config.max_position_pct
    max_shares_from_cap = int(max_position_value // entry_price)

    shares = min(shares_from_risk, max_shares_from_cap)
    capped = shares_from_risk > max_shares_from_cap

    position_value = shares * entry_price
    actual_risk_amount = shares * risk_per_share
    position_pct = position_value / account_size

    return PositionSize(
        shares=shares,
        risk_amount=actual_risk_amount,
        position_value=position_value,
        position_pct_of_account=position_pct,
        risk_per_share=risk_per_share,
        capped_by_max_position=capped,
    )


def calculate_position_size(
    account_size: float,
    entry_price: float,
    stop_loss: float,
    direction: str = "long",
    config: Config = DEFAULT_CONFIG,
) -> PositionSize:
    """
    Size a position so that if the stop-loss is hit, the loss equals
    config.risk_per_trade (default 1%) of account_size - capped by
    config.max_position_pct so a very tight stop can't size you into
    an oversized position.

    direction="long" requires stop_loss below entry_price.
    direction="short" requires stop_loss above entry_price.

    Raises ValueError on invalid inputs rather than silently producing
    a nonsensical size - a sizing bug is exactly the kind of thing that
    shouldn't fail quietly.
    """
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")

    if account_size <= 0:
        raise ValueError("account_size must be positive")

    if entry_price <= 0:
        raise ValueError("entry_price must be positive")

    if direction == "long" and stop_loss >= entry_price:
        raise ValueError(
            f"For a long position, stop_loss ({stop_loss}) must be below "
            f"entry_price ({entry_price})"
        )

    if direction == "short" and stop_loss <= entry_price:
        raise ValueError(
            f"For a short position, stop_loss ({stop_loss}) must be above "
            f"entry_price ({entry_price})"
        )

    risk_per_share = abs(entry_price - stop_loss)
    return _size_from_risk_per_share(account_size, entry_price, risk_per_share, config)


def calculate_position_size_rebalance_only(
    account_size: float,
    entry_price: float,
    assumed_adverse_move_pct: float = 0.08,
    direction: str = "long",
    config: Config = DEFAULT_CONFIG,
) -> PositionSize:
    """
    Size a position with no hard stop-loss - matches how the
    strategies were actually backtested (held until the next monthly
    rebalance, whatever price does in between).

    assumed_adverse_move_pct is NOT an exit order - nothing will
    automatically sell you out if the price moves this much. It's a
    risk buffer: "if this position moved against me by this % before
    the next rebalance, that's the loss I'm sizing against." Default
    8% is a reasonable starting assumption for a monthly-rebalanced
    position, not a rule - adjust it based on how volatile the actual
    stock is, or how much drawdown you're comfortable riding out
    between rebalances.

    Because there's no real stop price, direction doesn't change the
    math the way it does in calculate_position_size() - the risk
    buffer is symmetric (a % move against you, long or short).
    """
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")

    if account_size <= 0:
        raise ValueError("account_size must be positive")

    if entry_price <= 0:
        raise ValueError("entry_price must be positive")

    if not (0 < assumed_adverse_move_pct < 1):
        raise ValueError("assumed_adverse_move_pct must be between 0 and 1 (e.g. 0.08 for 8%)")

    risk_per_share = entry_price * assumed_adverse_move_pct
    return _size_from_risk_per_share(account_size, entry_price, risk_per_share, config)
