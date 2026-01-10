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
    Normalize external inputs to Side.
    Accepts Side, strings like "buy"/"sell"/"hold" (any case), otherwise HOLD.
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
