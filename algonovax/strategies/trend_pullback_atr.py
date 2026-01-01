from __future__ import annotations
import os
import traceback

import pandas as pd

from .indicators import atr, ema, rsi
from .types import Signal, Side
from .registry import register
from .types import Side, Signal


def generate_signal(
    df: pd.DataFrame,
    # 5m-friendly defaults (EMA200 is too slow unless you always have 1000+ bars)
    trend_ema: int = 120,
    pullback_ema: int = 21,
    rsi_n: int = 14,
    atr_n: int = 14,
    atr_k: float = 2.0,
    rr: float = 1.8,
    min_bars: int | None = None,
) -> Signal:
    try:
        if df is None or df.empty:
            return Signal(Side.HOLD, 0.0, "empty_df")

        req = ['close', 'high', 'low']
        missing = [c for c in req if c not in df.columns]
        if missing:
            return Signal(Side.HOLD, 0.0, f"missing_cols:{','.join(missing)}")

        need = min_bars if min_bars is not None else max(trend_ema, pullback_ema, rsi_n, atr_n) + 5
        if len(df) < need:
            return Signal(Side.HOLD, 0.0, f"warmup len={len(df)} need>={need}")

        close = df["close"]
        e_trend = ema(close, trend_ema)
        e_pull = ema(close, pullback_ema)
        r = rsi(close, rsi_n)
        a = atr(df, atr_n)

        if any(x.isna().iloc[-1] for x in (e_trend, e_pull, r, a)):
            return Signal(Side.HOLD, 0.0, "warmup_indicators")

        c0, c1 = float(close.iloc[-2]), float(close.iloc[-1])
        trend = float(e_trend.iloc[-1])
        pull0, pull1 = float(e_pull.iloc[-2]), float(e_pull.iloc[-1])
        r0, r1 = float(r.iloc[-2]), float(r.iloc[-1])
        atr1 = float(a.iloc[-1])

        # Long regime: price above trend EMA
        long_regime = c1 > trend

        # Pullback reclaim: below pull EMA then back above
        pullback_reclaim = (c0 < pull0) and (c1 > pull1)

        # Momentum confirm: RSI crosses above 50
        rsi_confirm = (r0 <= 50.0) and (r1 > 50.0)

        if long_regime and pullback_reclaim and rsi_confirm:
            entry = c1
            sl = max(0.0, entry - atr_k * atr1)
            tp = entry + rr * (entry - sl)
            return Signal(Side.BUY, 0.75, "trend_pullback_atr_long", stop_loss=sl, take_profit=tp)

        # Exit: trend break down
        if c0 >= trend and c1 < trend:
            return Signal(Side.SELL, 0.6, "trend_break_down")

        return Signal(Side.HOLD, 0.0, "no_setup")
    except Exception as e:
        traceback.print_exc()
        if os.getenv('ALGONOVAX_FAIL_FAST') == '1':
            raise
        traceback.print_exc()
        if os.getenv('ALGONOVAX_FAIL_FAST') == '1':
            raise
        return Signal(Side.HOLD, 0.0, f"error:{type(e).__name__}")
        traceback.print_exc()
        if os.getenv('ALGONOVAX_FAIL_FAST') == '1':
            raise



register("trend_pullback_atr", generate_signal)
