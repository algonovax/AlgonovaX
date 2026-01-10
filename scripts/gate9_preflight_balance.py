#!/usr/bin/env python3
import os
import sys
import ccxt


def die(msg: str, code: int = 2) -> None:
    print(f"PREFLIGHT_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def mk_exchange():
    key = os.getenv("BINANCEUS_API_KEY")
    sec = os.getenv("BINANCEUS_API_SECRET")
    if not key or not sec:
        die("Missing BINANCEUS_API_KEY/BINANCEUS_API_SECRET")
    return ccxt.binanceus({"apiKey": key, "secret": sec, "enableRateLimit": True})


def main():
    symbol = os.getenv("SYMBOL", "BTC/USDT")
    try:
        ex = mk_exchange()
        ex.load_markets()
        if symbol not in ex.markets:
            die(f"Symbol not found: {symbol}")

        m = ex.markets[symbol]
        quote = m.get("quote")
        base = m.get("base")
        print("PREFLIGHT_OK: market")
        print("symbol", symbol, "base", base, "quote", quote)

        bal = ex.fetch_balance()
        free = bal.get("free") or {}
        total = bal.get("total") or {}

        for a in [quote, "USD", "USDT"]:
            if not a:
                continue
            print(f"balance_free_{a}", free.get(a, 0))
            print(f"balance_total_{a}", total.get(a, 0))

        print("PREFLIGHT_PASS")
    except ccxt.BaseError as e:
        die(f"{type(e).__name__}: {e}", 3)


if __name__ == "__main__":
    main()
