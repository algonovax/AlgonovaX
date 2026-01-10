#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRADES_DIR = ROOT / "data" / "trades"
CANDLES_DIR = ROOT / "data" / "candles"
CANDLES_DIR.mkdir(parents=True, exist_ok=True)

PAIR = "XBTUSD"
INTERVAL_MIN = 5
INTERVAL_MS = INTERVAL_MIN * 60_000


def parse_trade(row) -> tuple[int, float, float]:
    # [price, volume, time, side, orderType, misc]
    price = float(row[0])
    vol = float(row[1])
    ts_ms = int(float(row[2]) * 1000.0)
    return ts_ms, price, vol


def main() -> int:
    src = TRADES_DIR / f"kraken_{PAIR}_trades_last30d.json"
    if not src.exists():
        print(f"ERROR: missing {src}")
        return 1

    trades = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(trades, list) or not trades:
        print("ERROR: trades empty/bad")
        return 1

    parsed = [parse_trade(t) for t in trades]
    parsed.sort(key=lambda x: x[0])

    candles = {}
    for ts_ms, price, vol in parsed:
        bucket = (ts_ms // INTERVAL_MS) * INTERVAL_MS
        c = candles.get(bucket)
        if c is None:
            candles[bucket] = [bucket, price, price, price, price, vol]  # ts,o,h,l,c,v
        else:
            # o unchanged
            if price > c[2]:
                c[2] = price
            if price < c[3]:
                c[3] = price
            c[4] = price
            c[5] += vol

    rows = [candles[k] for k in sorted(candles.keys())]
    if not rows:
        print("ERROR: no candles built")
        return 1

    start_ts = int(rows[0][0])
    end_ts = int(rows[-1][0])
    out = CANDLES_DIR / f"kraken_BTC_USD_{INTERVAL_MIN}m_{start_ts}_{end_ts}.json"
    out.write_text(json.dumps(rows), encoding="utf-8")
    print(f"WROTE {out} candles={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
