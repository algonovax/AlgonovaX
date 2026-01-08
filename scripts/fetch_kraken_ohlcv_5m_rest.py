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
    """
    Read an environment variable and return its trimmed value or a fallback.
    
    If the environment variable `name` is unset or contains only whitespace, returns `default`; otherwise returns the variable's value with surrounding whitespace removed.
    
    Parameters:
    	name (str): Environment variable name to read.
    	default (str): Fallback value returned when the variable is missing or empty.
    
    Returns:
    	str: Trimmed environment value, or `default` if unset or only whitespace.
    """
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else v.strip()

def ienv(name: str, default: int) -> int:
    """
    Read an integer value from an environment variable, returning a default if it's missing or empty.
    
    Parameters:
    	name (str): Name of the environment variable to read.
    	default (int): Value to return if the environment variable is not set or contains only whitespace.
    
    Returns:
    	int: The integer parsed from the environment variable, or `default` if the variable is absent or empty.
    """
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return int(v)

def symbol_to_fs(symbol: str) -> str:
    """
    Convert a trading symbol into a filesystem-safe uppercase string.
    
    Parameters:
        symbol (str): Trading symbol (e.g., "BTC/USD" or "eth-usd").
    
    Returns:
        fs_symbol (str): The input with '/' and '-' replaced by '_' and converted to uppercase.
    """
    return symbol.replace("/", "_").replace("-", "_").upper()

def kraken_pair(symbol: str) -> str:
    # Minimal mapping for your use-case
    """
    Convert a trading symbol into Kraken's pair naming convention.
    
    Transforms the input by uppercasing and removing any "/" characters. Special-cases the common BTCUSD symbol to Kraken's "XBTUSD" pair.
    
    Parameters:
        symbol (str): Trading symbol (e.g., "BTC/USD", "ethusd").
    
    Returns:
        pair (str): Kraken-formatted pair string (e.g., "XBTUSD", "ETHUSD").
    """
    sym = symbol.upper().replace("/", "")
    if sym == "BTCUSD":
        return "XBTUSD"
    return sym

def fetch_page(pair: str, interval: int, since_sec: int) -> Tuple[List[List[Any]], int]:
    """
    Fetch a single page of OHLC data for a Kraken trading pair.
    
    Parameters:
        pair (str): Kraken pair identifier (e.g., "XBTUSD").
        interval (int): OHLC interval in minutes (5 for 5-minute candles).
        since_sec (int): UNIX timestamp (seconds) to request data since.
    
    Returns:
        Tuple[List[List[Any]], int]: A tuple (rows, last) where `rows` is the list of OHLC rows returned by Kraken (each row follows Kraken's OHLC format: [time, open, high, low, close, vwap, volume, count]) and `last` is Kraken's returned "last" timestamp (seconds). If no rows are present, `rows` is an empty list.
    
    Raises:
        RuntimeError: If Kraken's API response contains an error array.
    """
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
    """
    Fetch 5-minute OHLCV candles from Kraken for a configured symbol and write them to a JSON file.
    
    Reads configuration from environment variables: SYMBOL (default "BTC/USD"), TIMEFRAME (must be "5m"), and DAYS (default 45). Pages through Kraken's OHLC endpoint from (now - DAYS) until current time, deduplicates by timestamp, converts rows to [time_ms, open, high, low, close, volume], sorts them, validates at least 1000 candles, and writes the result to data/candles/kraken_<symbol>_5m_<start>_<end>.json.
    
    Returns:
        int: `0` on success, `1` on error (invalid TIMEFRAME, insufficient candles, or fetch failures).
    """
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