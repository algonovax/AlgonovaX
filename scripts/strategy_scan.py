#!/usr/bin/env python3
import inspect
import os
import sys
from typing import Any, Dict

from algonovax.data.candles import load_candles_json
from algonovax.strategies import get
from algonovax.strategies.types import Side


def die(msg: str, code: int = 2) -> None:
    """
    Terminate the process after emitting a standardized scan failure message.
    
    Parameters:
        msg (str): Human-readable error message to print to stderr prefixed with "SCAN_FAIL:".
        code (int): Exit code used when terminating the process; defaults to 2.
    
    Raises:
        SystemExit: Exits the interpreter with the provided exit code.
    """
    print(f"SCAN_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _coerce(v: str):
    """
    Coerce an input string into a boolean, integer, or float when possible; otherwise return the trimmed string.
    
    Parameters:
        v (str): Input string; leading and trailing whitespace are ignored and comparisons are case-insensitive for boolean values.
    
    Returns:
        bool|int|float|str: `True` or `False` if the trimmed string equals "true" or "false" (case-insensitive); an `int` if it represents an integer; a `float` if it contains a decimal point and is numeric; otherwise the trimmed input string.
    """
    s = v.strip()
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    try:
        if "." in s:
            return float(s)
        return int(s)
    except Exception:
        return s


def build_kwargs_for(fn) -> Dict[str, Any]:
    """
    Builds keyword arguments for calling a strategy function from environment variables.
    
    Inspects the callable's signature and, for any parameter (except `df`) that matches a predefined environment-to-argument mapping, reads the corresponding environment variable (if set and non-empty), coerces its string value to bool/int/float/str, and includes it in the result.
    
    Parameters:
        fn (Callable): Target function whose parameters will be inspected.
    
    Returns:
        Dict[str, Any]: Mapping of argument names to coerced values derived from environment variables. Only includes arguments that exist on `fn` (excluding `df`) and whose environment variables are present and non-empty.
    """
    sig = inspect.signature(fn)
    allowed = set(sig.parameters.keys()) - {"df"}
    out: Dict[str, Any] = {}

    # Map ENV -> arg name
    env_map = {
        "TREND_EMA": "trend_ema",
        "FAST_EMA": "fast_ema",
        "RSI_N": "rsi_n",
        "RSI_ENTRY": "rsi_entry",
        "RSI_EXIT": "rsi_exit",
        "RSI_BUY": "rsi_buy",
        "RSI_SELL": "rsi_sell",
        "ATR_N": "atr_n",
        "ATR_K": "atr_k",
        "RR": "rr",
        "COOLDOWN_BARS": "cooldown_bars",
    }

    for envk, arg in env_map.items():
        if arg not in allowed:
            continue
        if envk in os.environ and os.environ[envk] != "":
            out[arg] = _coerce(os.environ[envk])

    return out


def main():
    """
    Run the configured trading strategy across a candles dataset and report detected buy/sell signals.
    
    Reads CANDLES_JSON (required), STRATEGY (default "ema_rsi_atr"), and LOOKBACK (default 180) from the environment, loads the candles JSON, and for each increasing prefix window calls the selected strategy with any additional keyword arguments discovered from environment variables. Prints BUY/SELL events as they are produced and a final SUMMARY with total rows, lookback, buy count, and sell count; prints USED_KWARGS if any strategy kwargs were supplied.
    
    Exits via die(...) on error conditions:
    - If CANDLES_JSON is not set, exits with code 2.
    - If the loaded dataframe is empty, exits with code 2.
    - If the strategy call raises TypeError, exits with code 3 and includes the kwargs in the message.
    - If the strategy call raises any other exception, exits with code 4 and includes the index and exception type/message.
    """
    path = os.getenv("CANDLES_JSON")
    strat = os.getenv("STRATEGY", "ema_rsi_atr")
    lookback = int(os.getenv("LOOKBACK", "180"))

    if not path:
        die("Set CANDLES_JSON=/path/to/candles.json")

    df = load_candles_json(path)
    if df.empty:
        die("Empty df")

    fn = get(strat)
    kwargs = build_kwargs_for(fn)

    start = max(0, len(df) - lookback)
    buys = sells = 0

    for i in range(start + 2, len(df) + 1):
        w = df.iloc[:i]
        try:
            sig = fn(w, **kwargs)
        except TypeError as e:
            die(f"TypeError calling strategy (kwargs={kwargs}): {e}", 3)
        except Exception as e:
            die(f"Strategy crash at i={i}: {type(e).__name__}: {e}", 4)

        if sig.side == Side.BUY:
            buys += 1
            print("BUY", i, sig.reason, "sl", sig.stop_loss, "tp", sig.take_profit)
        elif sig.side == Side.SELL:
            sells += 1
            print("SELL", i, sig.reason)

    print("SUMMARY", "rows", len(df), "lookback", lookback, "buys", buys, "sells", sells)
    if kwargs:
        print("USED_KWARGS", kwargs)


if __name__ == "__main__":
    main()