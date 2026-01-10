#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PY:-$ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || { echo "Missing venv python: $PY" >&2; exit 2; }

CONTENT='from __future__ import annotations

import pandas as pd

from .indicators import atr, ema, rsi
from .registry import register
from .types import Side, Signal


def generate_signal(
    df: pd.DataFrame,
    trend_ema: int = 100,
    fast_ema: int = 21,
    rsi_n: int = 14,
    rsi_entry: float = 45.0,
    rsi_exit: float = 60.0,
    atr_n: int = 14,
    atr_k: float = 2.2,
    rr: float = 1.5,
) -> Signal:
    try:
        if df is None or df.empty:
            return Signal(Side.HOLD, 0.0, "empty_df")

        need = max(trend_ema, fast_ema, rsi_n, atr_n) + 10
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

        fast_ok = (c1 >= fast1) or (c0 < fast0 and c1 > fast1)

        rsi_cross_up = (r0 <= rsi_entry) and (r1 > rsi_entry)
        rsi_cross_down = (r0 >= rsi_exit) and (r1 < rsi_exit)

        if long_regime and fast_ok and rsi_cross_up:
            entry = c1
            sl = max(0.0, entry - atr_k * atr1)
            tp = entry + rr * (entry - sl)
            return Signal(Side.BUY, 0.72, "ema_rsi_atr_buy_cross", stop_loss=sl, take_profit=tp)

        trend_break = (c0 >= trend1) and (c1 < trend1)
        if rsi_cross_down or trend_break:
            return Signal(Side.SELL, 0.55, "ema_rsi_atr_exit_cross")

        return Signal(Side.HOLD, 0.0, "no_setup")

    except Exception as e:
        return Signal(Side.HOLD, 0.0, f"error:{type(e).__name__}")


register("ema_rsi_atr", generate_signal)
'

"$PY" - <<PY
from pathlib import Path
p = Path("algonovax/strategies/ema_rsi_atr.py")
p.write_text(r"""$CONTENT""")
print("WROTE", p, "bytes", len(r"""$CONTENT"""))
PY

"$PY" -m py_compile algonovax/strategies/ema_rsi_atr.py
echo "OK: py_compile passed"
