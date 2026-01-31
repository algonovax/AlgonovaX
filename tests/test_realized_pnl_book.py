from __future__ import annotations

# TODO: fix this import to your real book class/module found via `rg`
# Example possibilities (you will replace with the real one):
# from algonovax.positions import PositionBook as Book
# from algonovax.book import Book
from algonovax.positions import PositionBook as Book  # <-- CHANGE THIS IF WRONG

from algonovax.events import OrderFilled


def test_realized_pnl_includes_fees():
    book = Book()

    buy = OrderFilled(symbol="BTC/USD", side="buy", qty=0.001, price=50010.0, fee=0.05001, ts=None)  # ts often ignored
    sell = OrderFilled(symbol="BTC/USD", side="sell", qty=0.001, price=50020.0, fee=0.05002, ts=None)

    r1 = float(book.apply_fill(buy) or 0.0)
    assert abs(r1 - 0.0) < 1e-12

    r2 = float(book.apply_fill(sell) or 0.0)

    # gross = (50020-50010)*0.001 = 0.01
    # fees = 0.05001+0.05002 = 0.10003
    # net = -0.09003
    assert abs(r2 - (-0.09003)) < 1e-6
