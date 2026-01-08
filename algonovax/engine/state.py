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
        """
        Return a dictionary representation of the dataclass suitable for serialization.
        
        Returns:
            dict[str, Any]: Mapping of field names to their values; nested dataclasses are converted to dictionaries.
        """
        return asdict(self)

def load_state(path: str, default: EngineState) -> EngineState:
    """
    Load engine state from a JSON file and apply its values onto the provided default EngineState.
    
    If the file does not exist or an error occurs while reading/parsing it, the provided `default` is returned unchanged. When present, the JSON may contain top-level numeric fields (`cash_quote`, `realized_pnl`, `unrealized_pnl`, `equity`, `last_price`, `day_start_equity`) and a nested `position` object with `side`, `qty_base`, and `entry_price`; those values are converted to the appropriate types and written into the returned EngineState.
    
    Parameters:
        path (str): Filesystem path to the JSON state file.
        default (EngineState): Base EngineState instance to update with values from the file; returned (possibly mutated) as the result.
    
    Returns:
        EngineState: The `default` EngineState with fields updated from the file when available, or the original `default` if the file is missing or an error occurs.
    """
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
    """
    Persist an EngineState to disk as compact UTF-8 JSON, creating parent directories if needed.
    
    Parameters:
        path (str): Filesystem path where the state JSON will be written.
        st (EngineState): EngineState instance to serialize and save.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st.to_dict(), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")