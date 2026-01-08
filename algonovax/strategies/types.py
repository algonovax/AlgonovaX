from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(frozen=True)
class Signal:
    side: Side
    confidence: float
    reason: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
def coerce_side(x: object) -> Side:
    """
    Normalize external inputs to a Side.
    
    Converts strings (case-insensitive, surrounding whitespace ignored) matching "buy", "sell", or "hold" to the corresponding Side. If the input is already a Side it is returned unchanged. If conversion fails or the value is unrecognized, returns Side.HOLD.
    
    Returns:
        Side: The corresponding Side value; `Side.HOLD` if the input is unrecognized or conversion fails.
    """
    if isinstance(x, Side):
        return x
    try:
        v = str(x).strip().lower()
    except Exception:
        return Side.HOLD
    if v in Side._value2member_map_:
        return Side(v)
    return Side.HOLD