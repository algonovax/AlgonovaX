from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from algonovax.events import OrderFilled


@dataclass
class Position:
    qty: float = 0.0
    avg_price: float = 0.0


class PositionBook:
    """
    Minimal long-only position book.
    - BUY increases qty and adjusts avg entry.
    - SELL decreases qty; realized pnl computed against avg entry.
    """

    def __init__(self) -> None:
        self._pos: Dict[str, Position] = {}

    def open_positions_count(self) -> int:
        return sum(1 for p in self._pos.values() if p.qty > 0)

    def apply_fill(self, f: OrderFilled) -> float:
        sym = f.symbol
        side = f.side.lower().strip()
        qty = float(f.qty)
        price = float(f.price)
        fee = float(f.fee)

        if qty <= 0:
            return 0.0

        p = self._pos.get(sym) or Position()
        realized = 0.0

        if side == "buy":
            # Include fee in cost basis (fee is in quote currency)
            new_qty = p.qty + qty
            if new_qty <= 0:
                p.qty = 0.0
                p.avg_price = 0.0
            else:
                buy_notional = price * qty + fee
                if p.qty > 0:
                    p.avg_price = ((p.avg_price * p.qty) + buy_notional) / new_qty
                else:
                    p.avg_price = buy_notional / qty
                p.qty = new_qty

        elif side == "sell":

            sell_qty = min(qty, p.qty)
            if sell_qty <= 0:
                # selling without position -> ignore for now (no shorts)
                realized = -fee
            else:
                realized = (price - p.avg_price) * sell_qty - fee
                p.qty = p.qty - sell_qty
                if p.qty <= 0:
                    p.qty = 0.0
                    p.avg_price = 0.0
        else:
            # unknown side
            return 0.0

        self._pos[sym] = p
        return realized
