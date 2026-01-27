from __future__ import annotations

import json
import os
import time
from pathlib import Path

import ccxt

ROOT = Path(__file__).resolve().parents[1]
CANDLES_DIR = ROOT / "data" / "candles"
CANDLES_DIR.mkdir(parents=True, exist_ok=True)

def die(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")

def tf_to_ms(tf: str) -> int:
    # supports 1m,5m,15m,1h
    if tf.endswith("m"):
        return int(tf[:-1]) * 60_000
    if tf.endswith("h"):
        return int(tf[:-1]) * 3_600_000
    raise ValueError(f"bad tf: {tf}")

def main() -> int:
    exchange_name = os.getenv("EXCHANGE", "kraken").lower()
    symbol = os.getenv("SYMBOL", "BTC/USD")
    tf = os.getenv("TF", "5m")
    days = int(os.getenv("DAYS", "90"))
    limit = int(os.getenv("LIMIT", "720"))  # kraken typical max
    sleep_ms = int(os.getenv("SLEEP_MS", "250"))

    ex = getattr(ccxt, exchange_name)({"enableRateLimit": True})

    now_ms = int(time.time() * 1000)
    since_ms = now_ms - days * 86400 * 1000
    step_ms = tf_to_ms(tf)

    all_rows: list[list[float]] = []
    seen = set()

    cursor = since_ms
    for _ in range(20000):
        rows = ex.fetch_ohlcv(symbol, timeframe=tf, since=cursor, limit=limit)
        if not rows:
            break

        added = 0
        max_ts = cursor
        for ts, o, h, lo, c, v in rows:
            if ts in seen:
                continue
            seen.add(ts)
            all_rows.append([float(ts), float(o), float(h), float(lo), float(c), float(v)])
            added += 1
            if ts > max_ts:
                max_ts = ts

        print(f"page since_ms={cursor} rows={len(rows)} added={added} max_ts={max_ts}")

        if added == 0:
            break

        next_cursor = max_ts + step_ms
        if next_cursor <= cursor:
            break
        cursor = next_cursor

        if cursor >= now_ms - step_ms:
            break

        time.sleep(sleep_ms / 1000.0)

    all_rows.sort(key=lambda r: r[0])
    if not all_rows:
        die("no candles fetched")

    start_ts_ms = int(all_rows[0][0])
    end_ts_ms = int(all_rows[-1][0])

    sym_file = symbol.replace("/", "_").replace("-", "_")
    out_path = CANDLES_DIR / f"{exchange_name}_{sym_file}_{tf}_{start_ts_ms}_{end_ts_ms}.json"

    payload = [{"ts": ts, "open": o, "high": h, "low": lo, "close": c, "volume": v} for ts, o, h, lo, c, v in all_rows]
    out_path.write_text(json.dumps(payload), encoding="utf-8")

    print(f"candles={len(payload)} last_ts_ms={end_ts_ms}")
    print(f"WROTE {out_path} candles={len(payload)}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
