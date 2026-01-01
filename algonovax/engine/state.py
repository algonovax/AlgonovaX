from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any
import json
from pathlib import Path

@dataclass
class Position:
    side: str = "flat"         # "long" or "flat"
    qty_base: float = 0.0
    entry_price: float = 0.0

@dataclass
class EngineState:
    mode: str
    pair: str
    cash_quote: float = 1000.0
    position: Position = field(default_factory=Position)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    equity: float = 1000.0
    last_price: float = 0.0
    day_start_equity: float = 1000.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def load_state(path: str, default: EngineState) -> EngineState:
    p = Path(path)
    if not p.exists():
        return default
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        pos = raw.get("position") or {}

        default.cash_quote = float(raw.get("cash_quote", default.cash_quote))
        default.realized_pnl = float(raw.get("realized_pnl", default.realized_pnl))
        default.unrealized_pnl = float(raw.get("unrealized_pnl", default.unrealized_pnl))
        default.equity = float(raw.get("equity", default.equity))
        default.last_price = float(raw.get("last_price", default.last_price))
        default.day_start_equity = float(raw.get("day_start_equity", default.day_start_equity))

        default.position.side = str(pos.get("side", default.position.side))
        default.position.qty_base = float(pos.get("qty_base", default.position.qty_base))
        default.position.entry_price = float(pos.get("entry_price", default.position.entry_price))

        return default
    except Exception:
        return default

def save_state(path: str, st: EngineState) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st.to_dict(), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
