#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# on_err writes a crash message with exit code, line number, and failed command to stderr, then exits with that code.
on_err() {
  local ec=$?
  echo "WRITE_PACK_CRASH exit_code=$ec line=${BASH_LINENO[0]} cmd=${BASH_COMMAND}" >&2
  exit "$ec"
}
trap on_err ERR

PY="${PY:-$ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || { echo "Missing venv python: $PY" >&2; exit 2; }

# write_file writes content to the specified path, creating parent directories as needed and printing a "WROTE" message with the written byte count.
write_file() {
  local path="$1"
  "$PY" - <<PY
from pathlib import Path
p = Path(r"""$path""")
p.parent.mkdir(parents=True, exist_ok=True)
content = r"""$2"""
p.write_text(content)
print("WROTE", p, "bytes", len(content))
PY
}

EMA_RSI_ATR='from __future__ import annotations

import pandas as pd

from .indicators import atr, ema, rsi
from .registry import register
from .types import Side, Signal


def generate_signal(
    df: pd.DataFrame,
    trend_ema: int = 100,
    fast_ema: int = 21,
    rsi_n: int = 14,
    rsi_buy: float = 42.0,
    rsi_sell: float = 68.0,
    atr_n: int = 14,
    atr_k: float = 2.2,
    rr: float = 1.5,
) -> Signal:
    try:
        if df is None or df.empty:
            return Signal(Side.HOLD, 0.0, "empty_df")

        need = max(trend_ema, fast_ema, rsi_n, atr_n) + 5
        if len(df) < need:
            return Signal(Side.HOLD, 0.0, f"warmup len={len(df)} need>={need}")

        close = df["close"]
        e_trend = ema(close, trend_ema)
        e_fast = ema(close, fast_ema)
        r = rsi(close, rsi_n)
        a = atr(df, atr_n)

        if any(x.isna().iloc[-1] for x in (e_trend, e_fast, r, a)):
            return Signal(Side.HOLD, 0.0, "warmup_indicators")

        c0, c1 = float(close.iloc[-2]), float(close.iloc[-1])
        trend1 = float(e_trend.iloc[-1])
        trend4 = float(e_trend.iloc[-4])
        fast0, fast1 = float(e_fast.iloc[-2]), float(e_fast.iloc[-1])
        r0, r1 = float(r.iloc[-2]), float(r.iloc[-1])
        atr1 = float(a.iloc[-1])

        trend_rising = trend1 >= trend4
        long_regime = (c1 > trend1) or (trend_rising and c1 > trend1 * 0.998)

        rsi_rebound = (r0 < rsi_buy) and (r1 > r0)
        fast_ok = (c1 >= fast1) or (c0 < fast0 and c1 > fast1)

        if long_regime and rsi_rebound and fast_ok:
            entry = c1
            sl = max(0.0, entry - atr_k * atr1)
            tp = entry + rr * (entry - sl)
            return Signal(Side.BUY, 0.70, "ema_rsi_atr_buy", stop_loss=sl, take_profit=tp)

        rsi_rollover = (r0 > rsi_sell) and (r1 < r0)
        trend_break = (c0 >= trend1) and (c1 < trend1)

        if rsi_rollover or trend_break:
            return Signal(Side.SELL, 0.55, "ema_rsi_atr_exit")

        return Signal(Side.HOLD, 0.0, "no_setup")

    except Exception as e:
        return Signal(Side.HOLD, 0.0, f"error:{type(e).__name__}")


register("ema_rsi_atr", generate_signal)
'

SCAN='#!/usr/bin/env python3
import os
import sys

from algonovax.data.candles import load_candles_json
from algonovax.strategies import get
from algonovax.strategies.types import Side


def die(msg: str, code: int = 2) -> None:
    print(f"SCAN_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


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

    start = max(0, len(df) - lookback)
    buys = sells = 0

    for i in range(start + 2, len(df) + 1):
        w = df.iloc[:i]
        sig = fn(w)
        if sig.side == Side.BUY:
            buys += 1
            print("BUY", i, sig.reason, "sl", sig.stop_loss, "tp", sig.take_profit)
        elif sig.side == Side.SELL:
            sells += 1
            print("SELL", i, sig.reason)

    print("SUMMARY", "rows", len(df), "lookback", lookback, "buys", buys, "sells", sells)


if __name__ == "__main__":
    main()
'

write_file "algonovax/strategies/ema_rsi_atr.py" "$EMA_RSI_ATR"
write_file "scripts/strategy_scan.py" "$SCAN"

chmod +x scripts/strategy_scan.py

"$PY" -m py_compile algonovax/strategies/ema_rsi_atr.py scripts/strategy_scan.py
echo "OK: py_compile passed"