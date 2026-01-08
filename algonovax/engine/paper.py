from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal
from algonovax.strategies.types import Side, coerce_side

Side = Literal["buy", "sell"]

@dataclass
class Fill:
    side: Side
    price: float
    qty_base: float
    fee_quote: float
    ts: int

def apply_slippage(price: float, side: Side, slippage_rate: float) -> float:
    """
    Adjusts a price by applying side-dependent slippage.
    
    Parameters:
        price (float): Reference price to adjust.
        side (Side): Trade side; "buy" increases the price, "sell" decreases the price.
        slippage_rate (float): Slippage fraction (e.g., 0.01 for 1%). If less than or equal to 0, no slippage is applied.
    
    Returns:
        float: Price adjusted for slippage; returns the original price if `slippage_rate` <= 0.
    """
    if slippage_rate <= 0:
        return price
    if coerce_side(side) == Side.BUY:

        return price * (1.0 + slippage_rate)
    return price * (1.0 - slippage_rate)

def compute_fee(notional_quote: float, fee_rate: float) -> float:
    """
    Calculate the trading fee from a notional quote value and a fee rate.
    
    Parameters:
        notional_quote (float): Total value in quote currency to which the fee rate is applied.
        fee_rate (float): Fee rate as a decimal fraction (e.g., 0.001 for 0.1%). Non-positive rates produce no fee.
    
    Returns:
        float: Fee amount in quote currency; `0.0` if `fee_rate` is less than or equal to zero.
    """
    if fee_rate <= 0:
        return 0.0
    return notional_quote * fee_rate