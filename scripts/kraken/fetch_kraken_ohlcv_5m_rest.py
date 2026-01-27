from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
CANDLES_DIR = ROOT / "data" / "candles"
CANDLES_DIR.mkdir(parents=True, exist_ok=True)

KRAKEN_OHLC = "https://api.kraken.com/0/public/OHLC"

def die(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")

def pick_rows(result: dict[str, Any]) -> list[list[Any]]:
    # Kraken returns {"last": "...", "<PAIRKEY>": [[...], ...]}
    for k, v in result.items():
        if k == "last":
            continue
        if isinstance(v, list) and v and isinstance(v[0], list) and len(v[0]) >= 8:
            return v
    return []

def fetch_ohlc_paginated(pair: str, interval_min: int, days: int, timeout_s: int = 30) -> list[dict[str, float]]:
    now_s = int(time.time())
    start_s = now_s - int(days) * 86400

    since = start_s
    seen: set[int] = set()
    out: list[dict[str, float]] = []

    # Kraken can be finicky; loop with a hard cap to avoid infinite paging
    for _ in range(5000):
        params = {"pair": pair, "interval": int(interval_min), "since": int(since)}
        r = requests.get(KRAKEN_OHLC, params=params, timeout=timeout_s)
        r.raise_for_status()
        j = r.json()

        if j.get("error"):
            die(f"kraken error: {j['error']}")

        result = j.get("result") or {}
        last = result.get("last")

        rows = pick_rows(result)
        if not rows:
            break

        added = 0
        max_ts = since

        for row in rows:
            ts_s = int(float(row[0]))
            if ts_s in seen:
                continue
            seen.add(ts_s)
            max_ts = max(max_ts, ts_s)
            out.append(
                {
                    "ts": float(ts_s * 1000.0),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[6]),
                }
            )
            added += 1

        print(f"page since={since} added={added} max_ts={max_ts} last={last}")

        if added == 0:
            break

        # Advance cursor: prefer max timestamp observed + 1
        since_next = max_ts + 1

        # If Kraken 'last' is provided and moves forward, use it if it's larger
        try:
            if last is not None:
                last_s = int(float(last))
                since_next = max(since_next, last_s)
        except Exception:
            pass

        if since_next <= since:
            break

        since = since_next

        # stop if we reached "now"
        if since >= now_s - 60:
            break

    out.sort(key=lambda r: r["ts"])
    return out

def main() -> int:
    pair = os.getenv("PAIR", "BTC/USD")
    interval_min = int(os.getenv("INTERVAL_MIN", "5"))
    days = int(os.getenv("DAYS", "7"))

    candles = fetch_ohlc_paginated(pair, interval_min, days)
    if not candles:
        die("no candles fetched")

    start_ts_ms = int(candles[0]["ts"])
    end_ts_ms = int(candles[-1]["ts"])

    pair_file = pair.replace("/", "_").replace("-", "_")
    tf = f"{interval_min}m"
    out_path = CANDLES_DIR / f"kraken_{pair_file}_{tf}_{start_ts_ms}_{end_ts_ms}.json"

    out_path.write_text(json.dumps(candles), encoding="utf-8")
    print(f"candles={len(candles)} last_ts_ms={end_ts_ms}")
    print(f"WROTE {out_path} candles={len(candles)}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
