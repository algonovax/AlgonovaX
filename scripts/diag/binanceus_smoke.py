from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

import ccxt


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    symbol = (sys.argv[1] if len(sys.argv) > 1 else "BTC/USDT").upper()
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "1m"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    ex = ccxt.binanceus({"enableRateLimit": True})

    t0 = time.time()
    try:
        t = ex.fetch_ticker(symbol)
        o = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        payload = {"ts": utc_iso(), "ok": False, "err": repr(e)}
        print(json.dumps(payload, separators=(",", ":")))
        return 2
    finally:
        try:
            ex.close()
        except Exception:
            pass

    dt_ms = int((time.time() - t0) * 1000)

    payload = {
        "ts": utc_iso(),
        "ok": True,
        "exchange": "binanceus",
        "symbol": symbol,
        "timeframe": timeframe,
        "latency_ms": dt_ms,
        "ticker": {
            "bid": t.get("bid"),
            "ask": t.get("ask"),
            "last": t.get("last"),
            "baseVolume": t.get("baseVolume"),
            "quoteVolume": t.get("quoteVolume"),
            "timestamp": t.get("timestamp"),
        },
        "ohlcv_tail": o[-3:],
    }
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
