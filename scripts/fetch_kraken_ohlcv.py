#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "data" / "candles"
OUTDIR.mkdir(parents=True, exist_ok=True)

KRAKEN_OHLC = "https://api.kraken.com/0/public/OHLC"

# Kraken uses XBT for BTC in many pairs
PAIR = "XBTUSD"
INTERVAL_MIN = 5

MS_PER_DAY = 24 * 60 * 60 * 1000
SEC_PER_MIN = 60

def fetch_ohlc_kraken(pair: str, interval_min: int, days: int) -> list[list[float]]:
    """
    Fetch OHLC candles from Kraken for a given trading pair and lookback window, returning normalized, deduplicated candle rows.
    
    Parameters:
        pair (str): Kraken asset pair symbol (e.g., "XBTUSD").
        interval_min (int): Candle interval in minutes.
        days (int): Number of days of historical data to fetch (lookback window).
    
    Returns:
        list[list[float]]: A list of candles sorted by timestamp ascending and deduplicated. Each candle is a list in the form
            [timestamp_ms, open, high, low, close, volume].
    
    Raises:
        RuntimeError: If an HTTP request fails or the Kraken API returns an error.
    """
    now_ms = int(time.time() * 1000)
    since_ms = now_ms - days * MS_PER_DAY

    # Kraken 'since' is in seconds
    since_sec = since_ms // 1000

    out: list[list[float]] = []
    last = since_sec
    stagnant = 0

    while True:
        params = {"pair": pair, "interval": interval_min, "since": last}
        try:
            r = requests.get(KRAKEN_OHLC, params=params, timeout=30)
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        except Exception as e:
            raise RuntimeError(f"HTTP error: {e}") from e

        if data.get("error"):
            raise RuntimeError(f"Kraken API error: {data['error']}")

        result = data.get("result") or {}
        last_next = result.get("last")
        # find the first non-'last' key (pair key)
        pair_key = next((k for k in result.keys() if k != "last"), None)
        rows = result.get(pair_key) if pair_key else None
        if not isinstance(rows, list) or not rows:
            stagnant += 1
            if stagnant >= 5:
                break
            # nudge cursor forward
            last += interval_min * SEC_PER_MIN
            time.sleep(1.0)
            continue

        stagnant = 0

        # rows are [time, open, high, low, close, vwap, volume, count]
        # normalize to [ts_ms, o, h, l, c, v]
        appended = 0
        last_ts_sec = None
        for row in rows:
            try:
                ts_sec = int(row[0])
                o = float(row[1]); h = float(row[2]); l = float(row[3]); c = float(row[4]); v = float(row[6])
            except Exception:
                continue

            ts_ms = ts_sec * 1000
            # skip anything before our desired since_ms
            if ts_ms < since_ms:
                continue
            out.append([ts_ms, o, h, l, c, v])
            appended += 1
            last_ts_sec = ts_sec

        # de-dupe + sort occasionally
        if len(out) and (len(out) % 5000 == 0):
            out = sorted({r[0]: r for r in out}.values(), key=lambda x: x[0])

        # progress
        if appended > 0:
            print(f"candles={len(out)} last_ts_ms={out[-1][0]}")

        if not isinstance(last_next, int):
            # fallback: advance by last candle time
            if last_ts_sec is None:
                break
            last = last_ts_sec + interval_min * SEC_PER_MIN
        else:
            last = last_next

        # stop when we're close to now
        if out and (now_ms - out[-1][0] < 2 * interval_min * 60_000):
            break

        # be polite
        time.sleep(1.0)

    # final de-dupe/sort
    out = sorted({r[0]: r for r in out}.values(), key=lambda x: x[0])
    return out

def main() -> int:
    """
    Fetch OHLC candles for the configured pair and interval, write them to a JSON file under OUTDIR, and report status.
    
    Writes a file named kraken_BTC_USD_<interval>m_<start_ts>_<end_ts>.json containing the fetched candles and prints progress or error messages.
    
    Returns:
        int: 0 on success, 1 if no candles were fetched.
    """
    days = 90
    rows = fetch_ohlc_kraken(PAIR, INTERVAL_MIN, days)
    if not rows:
        print("ERROR: no candles fetched")
        return 1

    start_ts = int(rows[0][0])
    end_ts = int(rows[-1][0])
    out_path = OUTDIR / f"kraken_BTC_USD_{INTERVAL_MIN}m_{start_ts}_{end_ts}.json"
    out_path.write_text(json.dumps(rows), encoding="utf-8")
    print(f"WROTE {out_path} candles={len(rows)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())