#!/usr/bin/env python3
import os
import sys

from algonovax.data.candles import load_candles_json
from algonovax.strategies import get


def die(msg: str, code: int = 2) -> None:
    """
    Print an error message to standard error with a "SMOKE_FAIL: " prefix and terminate the process.
    
    Parameters:
        msg (str): Message to print after the "SMOKE_FAIL: " prefix.
        code (int): Exit code to use when terminating the process.
    
    Raises:
        SystemExit: Raised with the provided exit code to terminate the process.
    """
    print(f"SMOKE_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main():
    """
    Run a smoke test for a trading strategy using candles data specified in the environment.
    
    Reads the CANDLES_JSON environment variable for a path to candles JSON and STRATEGY (default "sma_cross") for the strategy name. If CANDLES_JSON is not set, exits with an error message. Loads the candles data, exits with a formatted error on failure, retrieves the named strategy, executes it with the loaded data, and prints the strategy's returned signal to stdout.
    """
    path = os.getenv("CANDLES_JSON")
    strat = os.getenv("STRATEGY", "sma_cross")

    if not path:
        die("Set CANDLES_JSON=/path/to/candles.json")

    try:
        df = load_candles_json(path)
    except Exception as e:
        die(f"load_candles_json error: {type(e).__name__}: {e}")

    fn = get(strat)
    sig = fn(df)
    print(sig)


if __name__ == "__main__":
    main()