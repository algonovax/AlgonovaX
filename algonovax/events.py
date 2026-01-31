from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OrderFilled:
    symbol: str
    side: str          # "buy" | "sell"
    qty: float
    price: float
    fee: float
    ts: datetime
