#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import os
from pathlib import Path
from typing import List

import ccxt

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "candles"

def senv(name: str, default: str) -> str:
    """
    Read an environment variable and return a fallback when it's missing or empty.
    
    Parameters:
    	name: The environment variable name to read.
    	default: The fallback value to return if the environment variable is missing or contains only whitespace.
    
    Returns:
    	`default` if the environment variable is not set or is empty/whitespace after trimming, otherwise the environment value with surrounding whitespace removed.
    """
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else v.strip()

def ienv(name: str, default: int) -> int:
    """
    Read an environment variable and return its integer value, using a default when the variable is missing or empty.
    
    Parameters:
        name (str): Environment variable name to read.
        default (int): Integer to return if the environment variable is missing or contains only whitespace.
    
    Returns:
        int: The integer parsed from the environment variable, or `default` if the variable is not set or is empty/whitespace.
    """
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return int(v)

def symbol_to_fs(symbol: str) -> str:
    """
    Convert a trading symbol into a filesystem-friendly identifier.
    
    Parameters:
        symbol (str): Trading symbol (e.g., "BTC/USD" or "ETH-USD").
    
    Returns:
        fs_symbol (str): Uppercase symbol with "/" and "-" replaced by "_" (e.g., "BTC_USD").
    """
    return symbol.replace("/", "_").replace("-", "_").upper()

def main() -> int:
    """
    Fetches historical OHLCV candles from Kraken for a configured symbol and timeframe and saves them to a JSON file.
    
    Reads configuration from environment variables: `SYMBOL` (default "BTC/USD"), `TIMEFRAME` (default "5m"), and `DAYS` (default 30). Accumulates and deduplicates fetched candles, requires at least 1000 candles, creates the output directory if needed, and writes the collected candles to a JSON file whose name encodes the symbol, timeframe, and timestamp range.
    
    Returns:
        int: `0` on success (file written), `1` if fewer than 1000 candles were fetched.
    """
    symbol = senv("SYMBOL", "BTC/USD")
    timeframe = senv("TIMEFRAME", "5m")
    days = ienv("DAYS", 30)

    tf_ms = 5 * 60 * 1000
    now_ms = int(time.time() * 1000)
    since_ms = now_ms - days * 24 * 60 * 60 * 1000

    ex = ccxt.kraken({"enableRateLimit": True})

    all_rows: List[List[float]] = []
    cursor = since_ms
    last_ts = None

    # Kraken/CCXT sometimes returns overlapping windows. We dedupe by timestamp.
    seen = set()

    while True:
        rows = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=720)
        if not rows:
            break

        advanced = False
        for r in rows:
            ts = int(r[0])
            if ts in seen:
                continue
            seen.add(ts)
            all_rows.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])])
            last_ts = ts
            advanced = True

        if not advanced:
            break

        cursor = last_ts + tf_ms
        if last_ts >= now_ms - tf_ms:
            break

        time.sleep(0.25)

    all_rows.sort(key=lambda x: x[0])

    if len(all_rows) < 1000:
        print(f"ERROR: only {len(all_rows)} candles fetched; increase DAYS or check connectivity")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start_ts = int(all_rows[0][0])
    end_ts = int(all_rows[-1][0])
    out = OUT_DIR / f"kraken_{symbol_to_fs(symbol)}_{timeframe}_{start_ts}_{end_ts}.json"
    out.write_text(json.dumps(all_rows, indent=2), encoding="utf-8")

    print(f"WROTE {out}")
    print(f"candles={len(all_rows)} start={start_ts} end={end_ts}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())