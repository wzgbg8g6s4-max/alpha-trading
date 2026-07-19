"""
Position sizing.

Deliberately lightweight - full portfolio management (sector exposure,
cash allocation across many simultaneous positions, correlation
between holdings) is a bigger job for later. This answers one question
at a time: "given my account size, this stock's entry and stop-loss
price, how many shares does my risk-per-trade rule actually allow."
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
