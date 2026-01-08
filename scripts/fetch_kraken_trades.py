#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "data" / "trades"
OUTDIR.mkdir(parents=True, exist_ok=True)

TRADES_URL = "https://api.kraken.com/0/public/Trades"
PAIR = "XBTUSD"

NS_PER_SEC = 1_000_000_000
NS_PER_DAY = 24 * 60 * 60 * NS_PER_SEC

def fetch_trades(pair: str, days: int, sleep_s: float = 1.0, max_pages: int = 20000) -> list[list[Any]]:
    """
    Fetch historical trade rows for a given Kraken trading pair over the past `days` days.
    
    Requests paginated trade data from Kraken's public Trades endpoint starting from now - days, iterating until no new data, repeated stagnation, or reaching `max_pages`, and returns the accumulated trade rows.
    
    Parameters:
        pair (str): Kraken trading pair identifier (e.g., "XBTUSD").
        days (int): Number of days in the past to include in the fetch window.
        sleep_s (float): Seconds to sleep between requests to avoid rate limits.
        max_pages (int): Maximum number of paginated requests to perform.
    
    Returns:
        list[list[Any]]: A list of trade rows returned by the Kraken API, where each element is a row as provided by the API.
    
    Raises:
        RuntimeError: If the Kraken API returns an error or the response format is invalid.
    """
    now_ns = int(time.time() * NS_PER_SEC)
    since_ns = now_ns - days * NS_PER_DAY

    out: list[list[Any]] = []
    since = since_ns
    pages = 0
    stagnant = 0

    while pages < max_pages:
        r = requests.get(TRADES_URL, params={"pair": pair, "since": str(since)}, timeout=30)
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

        if rows:
            out.extend(rows)
            stagnant = 0
        else:
            stagnant += 1
            if stagnant >= 8:
                break

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
            print(f"pages={pages} trades={len(out)} since={since}")

        time.sleep(sleep_s)

    return out

def main() -> int:
    """
    Fetches recent trades for the configured PAIR over a 30-day window and writes them to the repository's data/trades directory.
    
    If trades are retrieved, writes the JSON file 'kraken_<PAIR>_trades_last30d.json' in OUTDIR and returns 0. If no trades are fetched, prints an error and returns 1.
    
    Returns:
        int: Exit code — `0` on success, `1` when no trades were fetched.
    """
    days = 30
    trades = fetch_trades(PAIR, days=days)
    if not trades:
        print("ERROR: no trades fetched")
        return 1

    out_path = OUTDIR / f"kraken_{PAIR}_trades_last{days}d.json"
    out_path.write_text(json.dumps(trades), encoding="utf-8")
    print(f"WROTE {out_path} trades={len(trades)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())