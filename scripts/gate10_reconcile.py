#!/usr/bin/env python3
import os
import sys
import ccxt

def die(msg: str, code: int = 2) -> None:
    """
    Prints an error message prefixed with "GATE10_FAIL:" to stderr and terminates the process with the specified exit code.
    
    Parameters:
        msg (str): The error message to print after the "GATE10_FAIL:" prefix.
        code (int): Exit code to use when terminating the process (default 2).
    
    Raises:
        SystemExit: Always raised to exit the process with the given code.
    """
    print(f"GATE10_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)

def mk_exchange():
    """
    Create and return a configured ccxt Binance US exchange client.
    
    Reads BINANCEUS_API_KEY and BINANCEUS_API_SECRET from the environment and exits the process with a GATE10_FAIL message if either is missing.
    
    Returns:
        ccxt.binanceus: A Binance US exchange instance configured with the environment API key and secret and rate limiting enabled.
    """
    key = os.getenv("BINANCEUS_API_KEY")
    sec = os.getenv("BINANCEUS_API_SECRET")
    if not key or not sec:
        die("Missing BINANCEUS_API_KEY/BINANCEUS_API_SECRET")
    return ccxt.binanceus({"apiKey": key, "secret": sec, "enableRateLimit": True})

def main():
    """
    Run the reconciliation check: validate symbol, ensure no open orders, and report free balances.
    
    Loads the configured Binance US exchange, verifies the target SYMBOL exists, aborts if any open orders remain, fetches free balances for the market's base and quote currencies, prints status and balance lines, and enforces MIN_USDT when the quote is USDT. Exits the process with a non-zero code on error conditions (including CCXT errors, which cause exit code 3).
    """
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