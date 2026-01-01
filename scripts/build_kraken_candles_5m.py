#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "candles"


def senv(name: str, default: str) -> str:
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else v.strip()


def ienv(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return int(v)


def symbol_to_fs(symbol: str) -> str:
    return symbol.replace("/", "_").replace("-", "_").upper()


def parse_trade(t: Any) -> Tuple[int, float, float]:
    if isinstance(t, (list, tuple)) and len(t) >= 3:
        return int(t[0]), float(t[1]), float(t[2])

    if isinstance(t, dict):
        ts = t.get("timestamp") or t.get("time") or t.get("ts") or t.get("t")
        if ts is None:
            raise ValueError("trade missing timestamp")
        price = t.get("price") or t.get("p")
        if price is None:
            raise ValueError("trade missing price")
        vol = t.get("amount") or t.get("volume") or t.get("qty") or t.get("v")
        if vol is None:
            vol = 0.0
        return int(ts), float(price), float(vol)

    raise TypeError(f"Unknown trade type: {type(t)}")


def floor_ts(ts_ms: int, tf_ms: int) -> int:
    return (ts_ms // tf_ms) * tf_ms


def build_ohlcv(trades: List[Any], timeframe_ms: int) -> List[List[float]]:
    buckets: Dict[int, List[Tuple[int, float, float]]] = {}

    for tr in trades:
        ts, price, vol = parse_trade(tr)
        b = floor_ts(ts, timeframe_ms)
        buckets.setdefault(b, []).append((ts, price, vol))

    out: List[List[float]] = []
    for b in sorted(buckets.keys()):
        rows = sorted(buckets[b], key=lambda x: x[0])
        o = rows[0][1]
        c = rows[-1][1]
        h = max(r[1] for r in rows)
        l = min(r[1] for r in rows)
        v = sum(r[2] for r in rows)
        out.append([int(b), float(o), float(h), float(l), float(c), float(v)])

    return out


def main() -> int:
    trades_file = senv("TRADES_FILE", "")
    if not trades_file:
        print("ERROR: TRADES_FILE env var is required (path to trades json)")
        return 1

    exchange = senv("EXCHANGE", "kraken").lower()
    symbol = senv("SYMBOL", "BTC/USD")
    timeframe = senv("TIMEFRAME", "5m").lower()
    tf_ms = ienv("TF_MS", 5 * 60 * 1000)

    p = Path(trades_file).expanduser()
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    if not p.exists():
        print(f"ERROR: trades file not found: {p}")
        return 1

    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: failed reading trades json: {e}")
        return 1

    if isinstance(obj, list):
        trades = obj
    elif isinstance(obj, dict):
        for k in ("trades", "data", "result"):
            if k in obj and isinstance(obj[k], list):
                trades = obj[k]
                break
        else:
            print("ERROR: trades json dict has no list under trades/data/result")
            return 1
    else:
        print("ERROR: trades json must be list or dict")
        return 1

    if len(trades) < 1000:
        print(f"ERROR: only {len(trades)} trades found; need more data")
        return 1

    candles = build_ohlcv(trades, tf_ms)
    if len(candles) < 1000:
        print(f"ERROR: only {len(candles)} candles built; need more data")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start_ts = int(candles[0][0])
    end_ts = int(candles[-1][0])
    out = OUT_DIR / f"{exchange}_{symbol_to_fs(symbol)}_{timeframe}_{start_ts}_{end_ts}.json"

    out.write_text(json.dumps(candles, indent=2), encoding="utf-8")
    print(f"WROTE {out}")
    print(f"candles={len(candles)} start={start_ts} end={end_ts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
