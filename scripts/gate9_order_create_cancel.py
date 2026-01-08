#!/usr/bin/env python3
import os
import sys
import time
from decimal import Decimal, ROUND_DOWN

import ccxt

def die(msg: str, code: int = 2) -> None:
    """
    Prints a standardized failure message to stderr and exits the process with the given code.
    
    Parameters:
        msg (str): Human-readable failure message appended after the "GATE9_FAIL:" prefix.
        code (int): Process exit code used when terminating (default 2).
    
    Raises:
        SystemExit: Terminates the program with the provided exit code.
    """
    print(f"GATE9_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)

def qd(x: Decimal, step: Decimal) -> Decimal:
    # quantize down to step (floor)
    """
    Quantizes a Decimal value down to the nearest multiple of a given step.
    
    Parameters:
        x (Decimal): The value to quantize.
        step (Decimal): The step size to quantize to; if less than or equal to zero, `x` is returned unchanged.
    
    Returns:
        Decimal: The largest multiple of `step` that is less than or equal to `x` (or `x` unchanged when `step` <= 0).
    """
    if step <= 0:
        return x
    return (x / step).to_integral_value(rounding=ROUND_DOWN) * step

def d(x) -> Decimal:
    """
    Convert a value to Decimal using its string representation.
    
    Parameters:
        x: The value to convert (commonly int, float, or str).
    
    Returns:
        Decimal: Decimal representation of `x`.
    """
    return Decimal(str(x))

def mk_exchange(name: str):
    """
    Create and configure a CCXT exchange instance for the given exchange name.
    
    Parameters:
        name (str): Exchange identifier; supported values are "binance", "binanceus", or "binance_us" (case-insensitive).
    
    Description:
        - For "binanceus" / "binance_us": reads BINANCEUS_API_KEY and BINANCEUS_API_SECRET from the environment and returns a ccxt.binanceus instance with rate limiting enabled. Exits via die() if credentials are missing.
        - For "binance": reads BINANCE_API_KEY and BINANCE_API_SECRET from the environment and returns a ccxt.binance instance with rate limiting enabled. If the exchange instance supports sandbox mode and the MODE environment variable (default "testnet") is "testnet", sandbox mode is enabled. Exits via die() if credentials are missing.
        - For any other name: exits via die() indicating the exchange is unsupported.
    
    Returns:
        ccxt.Exchange: A configured CCXT exchange instance.
    """
    name = name.lower()
    if name in ("binanceus", "binance_us"):
        key = os.getenv("BINANCEUS_API_KEY")
        sec = os.getenv("BINANCEUS_API_SECRET")
        if not key or not sec:
            die("Missing BINANCEUS_API_KEY/BINANCEUS_API_SECRET")
        return ccxt.binanceus({"apiKey": key, "secret": sec, "enableRateLimit": True})
    if name == "binance":
        key = os.getenv("BINANCE_API_KEY")
        sec = os.getenv("BINANCE_API_SECRET")
        if not key or not sec:
            die("Missing BINANCE_API_KEY/BINANCE_API_SECRET")
        ex = ccxt.binance({"apiKey": key, "secret": sec, "enableRateLimit": True})
        mode = os.getenv("MODE", "testnet").lower()
        if hasattr(ex, "set_sandbox_mode") and mode == "testnet":
            ex.set_sandbox_mode(True)
        return ex
    die(f"Unsupported EXCHANGE={name}")

def main():
    """
    Prepare, place, cancel, and verify a test LIMIT BUY order on a CCXT-compatible exchange configured via environment variables.
    
    This function reads configuration from environment variables (notably EXCHANGE, MODE, ALLOW_LIVE_ORDER_TEST, SYMBOL, STAKE_QUOTE, and PRICE_MULT), loads the market, computes a price and amount according to market precision and limits, prints prepared order details, places a LIMIT BUY order, immediately cancels it, and verifies the cancellation. It emits GATE9_OK and GATE9_PASS messages on success and calls die(...) to abort with a non-zero exit code on validation or execution failures.
    """
    ex_name = os.getenv("EXCHANGE", "binanceus")
    mode = os.getenv("MODE", "testnet").lower()

    if mode == "live" and os.getenv("ALLOW_LIVE_ORDER_TEST") != "1":
        die("Refusing live order test. Set ALLOW_LIVE_ORDER_TEST=1 to override.")

    symbol = os.getenv("SYMBOL", "BTC/USDT")
    stake_quote = d(os.getenv("STAKE_QUOTE", "5"))  # USD/USDT to spend target
    price_mult = d(os.getenv("PRICE_MULT", "0.5"))  # 0.5 => 50% of last price (won't fill)

    try:
        ex = mk_exchange(ex_name)
        markets = ex.load_markets()
        if symbol not in markets:
            die(f"Symbol not found: {symbol}")

        m = markets[symbol]
        amt_step = d(m.get("precision", {}).get("amount") or "0")
        px_step = d(m.get("precision", {}).get("price") or "0")
        min_cost = d(((m.get("limits") or {}).get("cost") or {}).get("min") or "0")
        min_amt = d(((m.get("limits") or {}).get("amount") or {}).get("min") or "0")

        ticker = ex.fetch_ticker(symbol)
        last = d(ticker.get("last"))
        if last <= 0:
            die("Bad ticker last price")

        price = qd(last * price_mult, px_step) if px_step > 0 else (last * price_mult)
        if price <= 0:
            die("Computed price <= 0")

        # amount = stake_quote / price
        amount = stake_quote / price
        amount = qd(amount, amt_step) if amt_step > 0 else amount

        if amount <= 0:
            die("Computed amount <= 0 (stake too small for amount precision)")

        cost = amount * price
        if min_amt > 0 and amount < min_amt:
            die(f"Amount {amount} < min amount {min_amt}. Increase STAKE_QUOTE.")
        if min_cost > 0 and cost < min_cost:
            die(f"Cost {cost} < min cost {min_cost}. Increase STAKE_QUOTE.")

        print("GATE9_OK: prepared order")
        print("exchange", ex_name, "mode", mode)
        print("symbol", symbol)
        print("last", str(last))
        print("price", str(price))
        print("amount", str(amount))
        print("cost", str(cost))

        # Place LIMIT BUY
        order = ex.create_limit_buy_order(symbol, float(amount), float(price))
        oid = order.get("id")
        if not oid:
            die(f"Order id missing: {order}")

        print("GATE9_OK: created order_id", oid)

        # Cancel immediately
        canceled = ex.cancel_order(oid, symbol)
        print("GATE9_OK: cancel requested", canceled.get("status") or "unknown")

        # Verify order closed/canceled
        time.sleep(1.0)
        try:
            o = ex.fetch_order(oid, symbol)
            st = (o.get("status") or "").lower()
            print("GATE9_OK: fetch_order status", st or "unknown")
            if st not in ("canceled", "cancelled", "closed"):
                die(f"Order not canceled/closed. status={st}")
        except ccxt.OrderNotFound:
            # Some exchanges may not return it after cancel; acceptable.
            print("GATE9_OK: fetch_order -> OrderNotFound (acceptable)")

        print("GATE9_PASS")

    except ccxt.BaseError as e:
        die(f"{type(e).__name__}: {e}", 3)
    except Exception as e:
        die(f"{type(e).__name__}: {e}", 4)

if __name__ == "__main__":
    main()