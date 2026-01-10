from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Literal, Any

SideStr = Literal["buy", "sell"]


@dataclass(frozen=True)
class Intent:
    action: Literal["hold", "enter", "exit"]
    side: Optional[SideStr] = None
    reason: str = ""
    # optional sizing hints (engine may ignore)
    stake_quote: Optional[float] = None


class Strategy:
    name: str = "base"

    def on_start(self, state: dict[str, Any]) -> None:
        return

    def on_candle(self, candle: dict[str, Any], state: dict[str, Any]) -> Intent:
        return Intent(action="hold", reason="default")

    def on_stop(self, state: dict[str, Any]) -> None:
        return
