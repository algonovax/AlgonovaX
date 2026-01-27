from __future__ import annotations

import json
import os
from pathlib import Path


def load_candles(exchange: str, pair: str, tf: str) -> list[dict[str, float]]:
    p = os.getenv("GATE_CANDLES_JSON", "").strip()
    if not p:
        raise RuntimeError("Set GATE_CANDLES_JSON=/path/to/candles.json")

    fp = Path(p)
    if not fp.exists():
        raise FileNotFoundError(f"GATE_CANDLES_JSON not found: {fp}")

    data = json.loads(fp.read_text("utf-8"))
    out: list[dict[str, float]] = []
    for r in data:
        out.append(
            {
                "ts": float(r["ts"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r.get("volume", 0.0)),
            }
        )
    return out
