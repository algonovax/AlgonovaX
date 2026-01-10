#!/usr/bin/env python3
import os
import sys
import time
import ccxt


def die(msg: str, code: int = 2) -> None:
    print(f"GATE11_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def mk_exchange():
    key = os.getenv("BINANCEUS_API_KEY")
    sec = os.getenv("BINANCEUS_API_SECRET")
    if not key or not sec:
        die("Missing BINANCEUS_API_KEY/BINANCEUS_API_SECRET")
    return ccxt.binanceus({"apiKey": key, "secret": sec, "enableRateLimit": True})


def get_free(bal, asset: str) -> float:
    free = bal.get("free") or {}
    return float(free.get(asset, 0) or 0)


def main():
    mode = os.getenv("MODE", "live").lower()
    if mode != "live":
        die("Refusing: MODE must be live for Gate 11 (this is a real fill test).")
    if os.getenv("ALLOW_LIVE_FILL_TEST") != "1":
        die("Refusing: set ALLOW_LIVE_FILL_TEST=1 to proceed.")

    symbol = os.getenv("SYMBOL", "BTC/USDT")
    stake_quote = float(os.getenv("STAKE_QUOTE", "6"))  # USDT spend cap

    try:
        ex = mk_exchange()
        ex.load_markets()

        if symbol not in ex.markets:
            die(f"Symbol not found: {symbol}")

        m = ex.markets[symbol]
        base = m.get("base")
        quote = m.get("quote")
        if quote != "USDT":
            die(f"Gate11 expects USDT quote. Got quote={quote}")

        b0 = ex.fetch_balance()
        usdt0 = get_free(b0, "USDT")
        btc0 = get_free(b0, "BTC")

        if usdt0 < stake_quote:
            die(f"Insufficient USDT. free={usdt0} need>={stake_quote}")

        print("GATE11_OK: pre-balance")
        print("free_USDT", usdt0)
        print("free_BTC", btc0)

        # Use quoteOrderQty if supported by ccxt for this exchange
        params = {}
        if ex.has.get("createMarketBuyOrderRequiresPrice"):
            # Some exchanges require price for market buy; binance-style supports quoteOrderQty.
            params["quoteOrderQty"] = stake_quote

        print("GATE11_OK: placing market buy", symbol, "quote_spend", stake_quote)

        # amount is ignored when quoteOrderQty is provided; provide 0 safely
        order = (
            ex.create_market_buy_order(symbol, 0, params)
            if params
            else ex.create_market_buy_order(symbol, stake_quote / 100000.0)
        )
        oid = order.get("id")
        print("GATE11_OK: created order_id", oid or "unknown")

        time.sleep(2.0)

        b1 = ex.fetch_balance()
        usdt1 = get_free(b1, "USDT")
        btc1 = get_free(b1, "BTC")

        du = usdt1 - usdt0
        db = btc1 - btc0

        print("GATE11_OK: post-balance")
        print("free_USDT", usdt1)
        print("free_BTC", btc1)
        print("delta_USDT", du)
        print("delta_BTC", db)

        if db <= 0:
            die("BTC did not increase; fill handling not proven.")
        if du >= 0:
            die("USDT did not decrease; fill handling not proven.")

        print("GATE11_PASS")

    except ccxt.BaseError as e:
        die(f"{type(e).__name__}: {e}", 3)


if __name__ == "__main__":
    main()
