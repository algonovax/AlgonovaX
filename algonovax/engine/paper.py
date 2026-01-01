from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal

Side = Literal["buy", "sell"]

@dataclass
class Fill:
    side: Side
    price: float
    qty_base: float
    fee_quote: float
    ts: int

def apply_slippage(price: float, side: Side, slippage_rate: float) -> float:
    if slippage_rate <= 0:
        return price
    if side == "buy":
        return price * (1.0 + slippage_rate)
    return price * (1.0 - slippage_rate)

def compute_fee(notional_quote: float, fee_rate: float) -> float:
    if fee_rate <= 0:
        return 0.0
    return notional_quote * fee_rate
