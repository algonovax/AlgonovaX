from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import ccxt

from algonovax.utils.net import force_ipv4


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    force_ipv4()
    key = os.getenv("BINANCEUS_API_KEY", "")
    secret = os.getenv("BINANCEUS_API_SECRET", "")
    if not key or not secret:
        print(json.dumps({"ts": utc_iso(), "ok": False, "err": "missing BINANCEUS_API_KEY/SECRET"}, separators=(",", ":")))
        return 2

    ex = ccxt.binanceus(
        {
            "apiKey": key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        }
    )

    t0 = time.time()
    try:
        bal = ex.fetch_balance()
        payload = {
            "ts": utc_iso(),
            "ok": True,
            "exchange": "binanceus",
            "latency_ms": int((time.time() - t0) * 1000),
            "balances_nonzero": {k: v for k, v in (bal.get("total") or {}).items() if v},
        }
        print(json.dumps(payload, separators=(",", ":")))
        return 0
    except Exception as e:
        print(json.dumps({"ts": utc_iso(), "ok": False, "err": repr(e)}, separators=(",", ":")))
        return 1
    finally:
        try:
            ex.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
