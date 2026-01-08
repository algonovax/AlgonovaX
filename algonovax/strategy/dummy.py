from __future__ import annotations
from .base import Strategy, Intent

class DummyHold(Strategy):
    name = "dummy_hold"

    def on_candle(self, candle, state):
        """
        Signal to hold the trading position for the current candle.
        
        Parameters:
        	candle: Market data for the current candle (e.g., open/high/low/close, volume).
        	state: Strategy state object carrying persistent or session-specific data.
        
        Returns:
        	Intent: an Intent with `action` set to "hold" and `reason` set to "smoke test".
        """
        return Intent(action="hold", reason="smoke test")