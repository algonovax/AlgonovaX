from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "trades"
OUT_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://api.kraken.com/0/public/Trades"


def die(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def pick_trades(result: dict) -> tuple[list[list], str]:
    last = str(result.get("last") or "")
    for k, v in result.items():
        if k == "last":
            continue
        if isinstance(v, list):
            return v, last
    return [], last


def main() -> int:
    # Kraken asset code for spot BTC/USD is usually XBTUSD.
    pair = os.getenv("PAIR", "XBTUSD").strip()
    days = int(os.getenv("DAYS", "90"))
    sleep_ms = int(os.getenv("SLEEP_MS", "1200"))
    max_pages = int(os.getenv("MAX_PAGES", "500000"))

    now_s = int(time.time())
    start_s = now_s - days * 86400

    state_path = OUT_DIR / f"kraken_{pair}_trades_cursor_{days}d.state"
    out_path = OUT_DIR / f"kraken_{pair}_trades_{days}d_{now_s}.jsonl"

    # resume if state exists
    since = ""
    if state_path.exists():
        since = state_path.read_text("utf-8").strip()

    if not since:
        # Kraken 'since' for Trades is a trade ID in "nanosecond-ish" units.
        # Using start_s * 1e9 works as a practical starting point.
        since = str(int(start_s * 1_000_000_000))

    kept = 0
    seen = 0
    newest_ts_s = 0.0

    # append if resuming into existing out_path
    mode = "a" if out_path.exists() else "w"

    backoff_s = 0.0
    sess = requests.Session()

    with out_path.open(mode, encoding="utf-8") as f:
        for page in range(max_pages):
            try:
                params = {"pair": pair, "since": since}
                r = sess.get(URL, params=params, timeout=30)
                r.raise_for_status()
                j = r.json()

                if j.get("error"):
                    err = j["error"]
                    # rate limit
                    if any("Too many requests" in str(x) for x in err):
                        backoff_s = min(60.0, backoff_s * 1.5 + 2.0) if backoff_s else 3.0
                        time.sleep(backoff_s)
                        continue
                    die(f"kraken error: {err}")

                backoff_s = 0.0

                result = j.get("result") or {}
                trades, last = pick_trades(result)

                if not trades:
                    try:
                        print(f"page={page} no_trades; stopping")
                    except BrokenPipeError:
                        pass
                    break

                # trade row: [price, volume, time, side, ordertype, misc]
                page_kept = 0
                for t in trades:
                    seen += 1
                    ts_s = float(t[2])
                    newest_ts_s = max(newest_ts_s, ts_s)
                    if ts_s < start_s:
                        continue
                    rec = {"ts": int(ts_s * 1000.0), "price": float(t[0]), "volume": float(t[1])}
                    f.write(json.dumps(rec) + "\n")
                    kept += 1
                    page_kept += 1

                # persist cursor so we can resume safely
                if last and last != since:
                    since = last
                    state_path.write_text(since, "utf-8")
                else:
                    try:
                        print(f"page={page} cursor_stalled; stopping")
                    except BrokenPipeError:
                        pass
                    break

                try:
                    print(f"page={page} since={since} got={len(trades)} kept_total={kept} kept_page={page_kept} newest_ts={int(newest_ts_s)}")
                except BrokenPipeError:
                    pass

                # stop once we've reached near-now
                if newest_ts_s >= now_s - 30:
                    break

                time.sleep(max(0.0, sleep_ms / 1000.0))

            except KeyboardInterrupt:
                raise
            except BrokenPipeError:
                # stdout closed; keep going quietly
                continue
            except Exception as e:
                # transient network / JSON / etc: brief backoff and retry
                try:
                    print(f"warn: {type(e).__name__}: {e}; retrying after 5s")
                except BrokenPipeError:
                    pass
                time.sleep(5.0)
                continue

    try:
        print(f"WROTE {out_path} kept={kept} seen={seen} cursor={since}")
        print(f"STATE {state_path}")
    except BrokenPipeError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
