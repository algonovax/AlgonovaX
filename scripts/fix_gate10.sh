#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

on_err() {
  local ec=$?
  echo "FIX_GATE10_CRASH exit_code=$ec line=${BASH_LINENO[0]} cmd=${BASH_COMMAND}" >&2
  exit "$ec"
}
trap on_err ERR

cat > scripts/gate10_reconcile.py <<'PY'
#!/usr/bin/env python3
import os
import sys
import ccxt

def die(msg: str, code: int = 2) -> None:
    print(f"GATE10_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)

def mk_exchange():
    key = os.getenv("BINANCEUS_API_KEY")
    sec = os.getenv("BINANCEUS_API_SECRET")
    if not key or not sec:
        die("Missing BINANCEUS_API_KEY/BINANCEUS_API_SECRET")
    return ccxt.binanceus({"apiKey": key, "secret": sec, "enableRateLimit": True})

def main():
    symbol = os.getenv("SYMBOL", "BTC/USDT")
    min_usdt = float(os.getenv("MIN_USDT", "0.0"))

    try:
        ex = mk_exchange()
        ex.load_markets()

        if symbol not in ex.markets:
            die(f"Symbol not found: {symbol}")

        m = ex.markets[symbol]
        base = m.get("base")
        quote = m.get("quote")

        opens = ex.fetch_open_orders(symbol)
        if opens:
            die(f"Open orders remain: {len(opens)} (first_id={opens[0].get('id')})")

        bal = ex.fetch_balance()
        free = bal.get("free") or {}

        q_free = float(free.get(quote, 0) or 0)
        b_free = float(free.get(base, 0) or 0)

        print("GATE10_OK: no open orders")
        print("symbol", symbol, "base", base, "quote", quote)
        print(f"free_{quote}", q_free)
        print(f"free_{base}", b_free)

        if quote == "USDT" and q_free < min_usdt:
            die(f"USDT free {q_free} < MIN_USDT {min_usdt}")

        print("GATE10_PASS")

    except ccxt.BaseError as e:
        die(f"{type(e).__name__}: {e}", 3)

if __name__ == "__main__":
    main()
PY

chmod +x scripts/gate10_reconcile.py
echo "OK: rewrote scripts/gate10_reconcile.py"
