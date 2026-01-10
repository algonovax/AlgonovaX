from __future__ import annotations
from .base import Strategy, Intent


class DummyHold(Strategy):
    name = "dummy_hold"

    def on_candle(self, candle, state):
        return Intent(action="hold", reason="smoke test")
