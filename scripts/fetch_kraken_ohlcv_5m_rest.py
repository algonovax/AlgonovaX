#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

import requests

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

def kraken_pair(symbol: str) -> str:
    # Minimal mapping for your use-case
    sym = symbol.upper().replace("/", "")
    if sym == "BTCUSD":
        return "XBTUSD"
    return sym

def fetch_page(pair: str, interval: int, since_sec: int) -> Tuple[List[List[Any]], int]:
    url = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": pair, "interval": interval, "since": since_sec}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"Kraken error: {data['error']}")
    result = data["result"]
    last = int(result["last"])
    # result has dynamic key for the pair
    rows = None
    for k, v in result.items():
        if k != "last":
            rows = v
            break
    if rows is None:
        return [], last
    return rows, last

def main() -> int:
    symbol = senv("SYMBOL", "BTC/USD")
    timeframe = senv("TIMEFRAME", "5m")
    days = ienv("DAYS", 45)

    if timeframe != "5m":
        print("ERROR: this script is hardcoded for 5m. Set TIMEFRAME=5m.")
        return 1

    pair = kraken_pair(symbol)
    interval = 5

    now_sec = int(time.time())
    since_sec = now_sec - days * 24 * 60 * 60

    all_rows: List[List[float]] = []
    seen = set()
    cursor = since_sec
    last_cursor = None

    while True:
        rows, nxt = fetch_page(pair, interval, cursor)
        advanced = False

        for r in rows:
            # Kraken row: [time, open, high, low, close, vwap, volume, count]
            ts_sec = int(r[0])
            if ts_sec in seen:
                continue
            seen.add(ts_sec)
            all_rows.append([
                ts_sec * 1000,
                float(r[1]),
                float(r[2]),
                float(r[3]),
                float(r[4]),
                float(r[6]),  # volume
            ])
            advanced = True

        if not advanced:
            break

        if last_cursor == nxt:
            break
        last_cursor = nxt
        cursor = nxt

        # stop when we're basically at "now"
        if cursor >= now_sec - 60:
            break

        time.sleep(0.2)

    all_rows.sort(key=lambda x: x[0])

    if len(all_rows) < 1000:
        print(f"ERROR: only {len(all_rows)} candles fetched; likely connectivity or API limitation")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start_ts = int(all_rows[0][0])
    end_ts = int(all_rows[-1][0])
    out = OUT_DIR / f"kraken_{symbol_to_fs(symbol)}_5m_{start_ts}_{end_ts}.json"
    out.write_text(json.dumps(all_rows, indent=2), encoding="utf-8")

    print(f"WROTE {out}")
    print(f"candles={len(all_rows)} start={start_ts} end={end_ts}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
