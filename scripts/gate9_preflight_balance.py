#!/usr/bin/env python3
import os
import sys
import ccxt

def die(msg: str, code: int = 2) -> None:
    """
    Report a preflight failure message and terminate the process.
    
    Prints the provided message to standard error prefixed with "PREFLIGHT_FAIL: " and then raises SystemExit with the given exit code.
    
    Parameters:
        msg (str): Human-readable error message to emit.
        code (int): Exit code to use when terminating the process (default 2).
    
    Raises:
        SystemExit: Exits the process with the provided exit code.
    """
    print(f"PREFLIGHT_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)

def mk_exchange():
    """
    Create and return a configured Binance US CCXT exchange client.
    
    Reads BINANCEUS_API_KEY and BINANCEUS_API_SECRET from the environment and exits with a PREFLIGHT_FAIL message if either is missing. Returns a ccxt.binanceus instance configured with the provided API key, secret, and rate-limit enabled.
    
    Returns:
        ccxt.binanceus: A Binance US exchange client configured with the provided credentials and rate-limit enabled.
    """
    key = os.getenv("BINANCEUS_API_KEY")
    sec = os.getenv("BINANCEUS_API_SECRET")
    if not key or not sec:
        die("Missing BINANCEUS_API_KEY/BINANCEUS_API_SECRET")
    return ccxt.binanceus({"apiKey": key, "secret": sec, "enableRateLimit": True})

def main():
    """
    Run a preflight check against Binance US and print structured market and balance status lines.
    
    Reads the SYMBOL environment variable (default "BTC/USDT"), creates a Binance US exchange client, verifies the symbol exists in the exchange markets, prints a "PREFLIGHT_OK: market" line with symbol, base, and quote, fetches account balances and prints `balance_free_<CURRENCY>` and `balance_total_<CURRENCY>` for the market quote currency and for "USD" and "USDT" when present, then prints "PREFLIGHT_PASS". If a symbol is not found or a CCXT error occurs, the function calls the module's `die` handler (exiting with an error).
    """
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
        free = (bal.get("free") or {})
        total = (bal.get("total") or {})

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