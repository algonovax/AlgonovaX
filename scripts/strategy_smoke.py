#!/usr/bin/env python3
import os
import sys

from algonovax.data.candles import load_candles_json
from algonovax.strategies import get


def die(msg: str, code: int = 2) -> None:
    print(f"SMOKE_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main():
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
