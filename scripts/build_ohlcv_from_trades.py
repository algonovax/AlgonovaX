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
    """
    Parse a raw trade row into a timestamp (milliseconds), price, and volume.
    
    Parameters:
        row (Sequence): Trade row expected as [price, volume, time, side, orderType, misc].
            - price and volume may be strings or numbers.
            - time is seconds since the Unix epoch (string or number).
    
    Returns:
        tuple[int, float, float]: (timestamp_ms, price, volume)
            - timestamp_ms: integer milliseconds since the Unix epoch.
            - price: trade price as float.
            - volume: trade volume as float.
    """
    price = float(row[0])
    vol = float(row[1])
    ts_ms = int(float(row[2]) * 1000.0)
    return ts_ms, price, vol

def main() -> int:
    """
    Aggregate trades from the configured trades file into fixed-interval OHLCV candles and write the resulting candle array to a JSON file in CANDLES_DIR.
    
    The function reads trades from TRADES_DIR/kraken_{PAIR}_trades_last30d.json, validates and sorts them by timestamp, groups trades into buckets of INTERVAL_MS milliseconds producing candles with [timestamp, open, high, low, close, volume], and writes the list of candles to CANDLES_DIR with a filename that encodes the pair, interval (in minutes), start timestamp, and end timestamp.
    
    Returns:
        int: `0` on success; `1` if the source file is missing, the trades data is empty/invalid, or no candles could be built.
    """
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
            if price > c[2]: c[2] = price
            if price < c[3]: c[3] = price
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