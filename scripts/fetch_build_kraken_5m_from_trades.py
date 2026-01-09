#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
CANDLES_DIR = ROOT / "data" / "candles"
CANDLES_DIR.mkdir(parents=True, exist_ok=True)

TRADES_URL = "https://api.kraken.com/0/public/Trades"
PAIR = "XBTUSD"
INTERVAL_MIN = 5
INTERVAL_MS = INTERVAL_MIN * 60_000

NS_PER_SEC = 1_000_000_000
NS_PER_DAY = 24 * 60 * 60 * NS_PER_SEC

def parse_trade(row) -> tuple[int, float, float]:
    # Kraken trade row: [price, volume, time, side, orderType, misc]
    price = float(row[0])
    vol = float(row[1])
    ts_ms = int(float(row[2]) * 1000.0)
    return ts_ms, price, vol

def main() -> int:
    days = 30
    now_ns = int(time.time() * NS_PER_SEC)
    since_ns = now_ns - days * NS_PER_DAY

    candles: dict[int, list[float]] = {}  # bucket -> [ts,o,h,l,c,v]
    since = since_ns
    pages = 0
    stagnant = 0

    while True:
        r = requests.get(TRADES_URL, params={"pair": PAIR, "since": str(since)}, timeout=30)
        r.raise_for_status()
        data: dict[str, Any] = r.json()

        if data.get("error"):
            raise RuntimeError(f"Kraken API error: {data['error']}")

        result = data.get("result") or {}
        last = result.get("last")
        pair_key = next((k for k in result.keys() if k != "last"), None)
        rows = result.get(pair_key) if pair_key else None
        if not isinstance(rows, list):
            raise RuntimeError("Bad Trades response format")

        if not rows:
            stagnant += 1
            if stagnant >= 8:
                break
        else:
            stagnant = 0
            for t in rows:
                ts_ms, price, vol = parse_trade(t)
                bucket = (ts_ms // INTERVAL_MS) * INTERVAL_MS
                c = candles.get(bucket)
                if c is None:
                    candles[bucket] = [float(bucket), price, price, price, price, vol]
                else:
                    if price > c[2]: c[2] = price
                    if price < c[3]: c[3] = price
                    c[4] = price
                    c[5] += vol

        if not last:
            break
        last_i = int(last)
        if last_i <= since:
            stagnant += 1
            if stagnant >= 8:
                break
        since = last_i

        pages += 1
        if pages % 25 == 0:
            print(f"pages={pages} buckets={len(candles)} since={since}")

        time.sleep(1.0)

    if not candles:
        print("ERROR: no candles built")
        return 1

    rows_out = [candles[k] for k in sorted(candles.keys())]
    start_ts = int(rows_out[0][0])
    end_ts = int(rows_out[-1][0])

    out = CANDLES_DIR / f"kraken_BTC_USD_{INTERVAL_MIN}m_{start_ts}_{end_ts}.json"
    out.write_text(json.dumps([[int(r[0]), r[1], r[2], r[3], r[4], r[5]] for r in rows_out]), encoding="utf-8")
    print(f"WROTE {out} candles={len(rows_out)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
