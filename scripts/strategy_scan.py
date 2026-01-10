#!/usr/bin/env python3
import inspect
import os
import sys
from typing import Any, Dict

from algonovax.data.candles import load_candles_json
from algonovax.strategies import get
from algonovax.strategies.types import Side


def die(msg: str, code: int = 2) -> None:
    print(f"SCAN_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _coerce(v: str):
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

    print(
        "SUMMARY", "rows", len(df), "lookback", lookback, "buys", buys, "sells", sells
    )
    if kwargs:
        print("USED_KWARGS", kwargs)


if __name__ == "__main__":
    main()
