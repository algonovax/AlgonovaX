from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal, Any

Side = Literal["buy", "sell"]

@dataclass(frozen=True)
class Intent:
    action: Literal["hold", "enter", "exit"]
    side: Optional[Side] = None
    reason: str = ""
    # optional sizing hints (engine may ignore)
    stake_quote: Optional[float] = None

class Strategy:
    name: str = "base"

    def on_start(self, state: dict[str, Any]) -> None:
        """
        Called once when the strategy starts to initialize or modify runtime state.
        
        Parameters:
            state (dict[str, Any]): Mutable mapping for storing and sharing runtime data across the strategy's lifecycle methods.
        """
        return

    def on_candle(self, candle: dict[str, Any], state: dict[str, Any]) -> Intent:
        """
        Decides the strategy action for a single incoming market candle.
        
        Parameters:
            candle (dict[str, Any]): The latest market data point (e.g., open, high, low, close, volume) for the current candle.
            state (dict[str, Any]): Mutable strategy state shared across callbacks; may be read and updated by implementations.
        
        Returns:
            Intent: Intent containing the chosen action, optional side, human-readable reason, and optional stake_quote.
        """
        return Intent(action="hold", reason="default")

    def on_stop(self, state: dict[str, Any]) -> None:
        """
        Called when the strategy is stopped; override to perform any cleanup or finalization using the current runtime state.
        
        Parameters:
            state (dict[str, Any]): Mutable runtime state provided by the engine (shared across lifecycle methods).
        """
        return