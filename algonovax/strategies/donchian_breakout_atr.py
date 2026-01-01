from __future__ import annotations
import os
import traceback

import pandas as pd

from .indicators import atr, ema
from .types import Signal, Side
from .registry import register
from .types import Side, Signal


def _donchian(high: pd.Series, low: pd.Series, n: int) -> tuple[pd.Series, pd.Series]:
    hi = high.rolling(n, min_periods=n).max()
    lo = low.rolling(n, min_periods=n).min()
    return hi, lo


def generate_signal(
    df: pd.DataFrame,
    *,
    in_position: bool = False,
    entry_price: float | None = None,
    entry_index: int | None = None,

    # params
    trend_ema: int = 120,
    slope_bars: int = 8,
    donchian_n: int = 20,

    atr_n: int = 14,
    stop_k: float = 2.2,
    trail_k: float = 2.0,

    min_atr_pct: float = 0.0009,     # avoid dead chop
    max_hold_bars: int = 96,         # ~8h on 5m
    min_hold_bars: int = 6,

    breakout_buffer_atr: float = 0.10,  # require breakout by X*ATR
) -> Signal:
    try:
        if df is None or df.empty:
            return Signal(Side.HOLD, 0.0, "empty_df")

        req = ['close', 'high', 'low']
        missing = [c for c in req if c not in df.columns]
        if missing:
            return Signal(Side.HOLD, 0.0, f"missing_cols:{','.join(missing)}")

        need = max(trend_ema, donchian_n, atr_n) + max(10, slope_bars + 2)
        if len(df) < need:
            return Signal(Side.HOLD, 0.0, f"warmup len={len(df)} need>={need}")

        close = df["close"]
        high = df["high"]
        low = df["low"]

        e = ema(close, trend_ema)
        a = atr(df, atr_n)
        d_hi, d_lo = _donchian(high, low, donchian_n)

        if any(x.isna().iloc[-1] for x in (e, a, d_hi, d_lo)):
            return Signal(Side.HOLD, 0.0, "warmup_indicators")

        c0, c1 = float(close.iloc[-2]), float(close.iloc[-1])
        hi1 = float(d_hi.iloc[-2])   # use prior channel to avoid lookahead
        lo1 = float(d_lo.iloc[-2])
        atr1 = float(a.iloc[-1])
        e1 = float(e.iloc[-1])

        # trend + volatility regime
        slope_ok = float(e.iloc[-1]) > float(e.iloc[-1 - slope_bars])
        trend_ok = (c1 >= e1) and slope_ok
        atr_ok = (atr1 / max(1e-9, c1)) >= min_atr_pct

        if not atr_ok:
            return Signal(Side.HOLD, 0.0, "atr_dead")
        if not trend_ok and not in_position:
            return Signal(Side.HOLD, 0.0, "no_trend")

        # time stop (if scanner passes entry_index)
        if in_position and entry_index is not None:
            held = len(df) - entry_index
            if held >= max_hold_bars:
                return Signal(Side.SELL, 0.55, "time_stop")

        # trailing stop / hard stop based on ATR
        if in_position and entry_price is not None:
            hard_sl = entry_price - stop_k * atr1
            chand_sl = c1 - trail_k * atr1
            sl = max(hard_sl, chand_sl)

            if c1 <= sl:
                return Signal(Side.SELL, 0.72, "stop_hit", stop_loss=sl)

            if entry_index is not None and (len(df) - entry_index) < min_hold_bars:
                return Signal(Side.HOLD, 0.0, "min_hold")

            # break back into channel = exit signal
            if c0 >= lo1 and c1 < lo1:
                return Signal(Side.SELL, 0.55, "channel_fail")

            return Signal(Side.HOLD, 0.0, "manage")

        # entry: breakout above prior donchian high by buffer*ATR
        buf = breakout_buffer_atr * atr1
        breakout = (c0 <= hi1 + buf) and (c1 > hi1 + buf)

        if trend_ok and breakout:
            entry = c1
            sl = max(0.0, entry - stop_k * atr1)
            tp = entry + 1.5 * (entry - sl)
            return Signal(Side.BUY, 0.75, "donchian_breakout", stop_loss=sl, take_profit=tp)

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



register("donchian_breakout_atr", generate_signal)
