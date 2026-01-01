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
