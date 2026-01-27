from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
CANDLES_DIR = ROOT / "data" / "candles"
TRADES_DIR = ROOT / "data" / "trades"
CANDLES_DIR.mkdir(parents=True, exist_ok=True)
TRADES_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://api.kraken.com/0/public/Trades"

def die(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")

def pick_trades(result: dict[str, Any]) -> tuple[list[list[Any]], str]:
    last = str(result.get("last") or "")
    for k, v in result.items():
        if k == "last":
            continue
        if isinstance(v, list):
            return v, last
    return [], last

@dataclass
class Candle:
    ts_ms: int
    o: float
    h: float
    lo: float
    c: float
    v: float

def bucket_ts_ms(ts_ms: int, bucket_ms: int) -> int:
    return (ts_ms // bucket_ms) * bucket_ms

def main() -> int:
    pair = os.getenv("PAIR", "XBTUSD").strip()
    days = int(os.getenv("DAYS", "90"))
    interval_min = int(os.getenv("INTERVAL_MIN", "5"))
    sleep_ms = int(os.getenv("SLEEP_MS", "1200"))
    max_pages = int(os.getenv("MAX_PAGES", "300000"))

    bucket_ms = interval_min * 60_000
    now_s = int(time.time())
    start_s = now_s - days * 86400
    start_ms = start_s * 1000

    since_file = TRADES_DIR / f"kraken_{pair}_since.txt"
    candles_out = CANDLES_DIR / f"kraken_{pair}_{interval_min}m_{start_ms}_partial.json"

    since = "0"
    if since_file.exists():
        since = since_file.read_text("utf-8").strip() or "0"

    # buckets keyed by bucket open ts_ms
    buckets: dict[int, Candle] = {}

    # if partial candles exist, load and resume (optional)
    if candles_out.exists():
        try:
            existing = json.loads(candles_out.read_text("utf-8"))
            for r in existing:
                ts = int(float(r["ts"]))
                buckets[ts] = Candle(
                    ts_ms=ts,
                    o=float(r["open"]),
                    h=float(r["high"]),
                    l=float(r["low"]),
                    c=float(r["close"]),
                    v=float(r.get("volume", 0.0)),
                )
        except Exception:
            pass

    backoff_s = 1.0

    for page in range(max_pages):
        try:
            r = requests.get(URL, params={"pair": pair, "since": since}, timeout=30)
            r.raise_for_status()
            j = r.json()
        except Exception as e:
            print(f"warn: request_failed page={page} since={since} err={type(e).__name__}:{e}")
            time.sleep(backoff_s)
            backoff_s = min(backoff_s * 2.0, 60.0)
            continue

        errs = j.get("error") or []
        if errs:
            # Rate limit / too many requests -> backoff and retry same since
            if any("Too many requests" in str(x) for x in errs):
                print(f"rate_limit: page={page} since={since} sleeping={backoff_s:.1f}s")
                time.sleep(backoff_s)
                backoff_s = min(backoff_s * 2.0, 60.0)
                continue
            die(f"Kraken API error: {errs}")

        backoff_s = 1.0

        result = j.get("result") or {}
        trades, last = pick_trades(result)
        if not trades:
            print(f"done: no trades page={page}")
            break

        kept = 0
        newest_ts_ms = 0

        # trade row: [price, volume, time, side, ordertype, misc]
        for t in trades:
            ts_ms = int(float(t[2]) * 1000.0)
            newest_ts_ms = max(newest_ts_ms, ts_ms)
            if ts_ms < start_ms:
                continue
            price = float(t[0])
            vol = float(t[1])

            bts = bucket_ts_ms(ts_ms, bucket_ms)
            c = buckets.get(bts)
            if c is None:
                buckets[bts] = Candle(ts_ms=bts, o=price, h=price, l=price, c=price, v=vol)
            else:
                c.h = max(c.h, price)
                c.l = min(c.l, price)
                c.c = price
                c.v += vol
            kept += 1

        if last and last != since:
            since = last
            since_file.write_text(since, "utf-8")

        # periodic flush
        if page % 25 == 0:
            rows = [
                {"ts": float(c.ts_ms), "open": c.o, "high": c.h, "low": c.l, "close": c.c, "volume": c.v}
                for c in sorted(buckets.values(), key=lambda x: x.ts_ms)
            ]
            candles_out.write_text(json.dumps(rows), "utf-8")
            print(f"pages={page} buckets={len(buckets)} kept_trades={kept} since={since} newest_ts_ms={newest_ts_ms}")

        time.sleep(max(0.0, sleep_ms / 1000.0))

    # finalize file name with actual end ts
    rows = [
        {"ts": float(c.ts_ms), "open": c.o, "high": c.h, "low": c.l, "close": c.c, "volume": c.v}
        for c in sorted(buckets.values(), key=lambda x: x.ts_ms)
    ]
    if not rows:
        die("no candles produced")

    start_ts = int(rows[0]["ts"])
    end_ts = int(rows[-1]["ts"])
    final_path = CANDLES_DIR / f"kraken_{pair}_{interval_min}m_{start_ts}_{end_ts}.json"
    final_path.write_text(json.dumps(rows), "utf-8")
    print(f"WROTE {final_path} candles={len(rows)}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
