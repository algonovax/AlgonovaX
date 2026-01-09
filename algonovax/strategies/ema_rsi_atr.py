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
    *,
    in_position: bool = False,
    entry_price: float | None = None,
    entry_index: int | None = None,  # df length at entry (scanner passes)
    # --- entry gates ---
    trend_ema: int = 100,
    fast_ema: int = 21,
    rsi_n: int = 14,
    rsi_entry: float = 46.0,
    atr_n: int = 14,
    impulse_atr: float = 0.35,
    min_atr_pct: float = 0.0008,
    trend_slope_bars: int = 6,
    fast_slope_bars: int = 4,
    rsi_cross_lookback: int = 8,
    # pullback/extension guard (NEW)
    max_extension_atr: float = 0.60,   # entry must be within this ATR above fast EMA
    min_pullback_atr: float = -0.10,   # allow tiny dip below fast
    # --- risk/exit model ---
    atr_k: float = 2.2,
    trail_k: float = 2.0,
    rr: float = 1.5,
    be_r: float = 1.0,                 # move SL to entry after +be_r * R
    min_hold_bars: int = 6,
    max_hold_bars: int = 72,
    exit_trend_break: float = 0.997,
) -> Signal:
    try:
        if df is None or df.empty:
            return Signal(Side.HOLD, 0.0, "empty_df")

        req = ['close', 'high', 'low']
        missing = [c for c in req if c not in df.columns]
        if missing:
            return Signal(Side.HOLD, 0.0, f"missing_cols:{','.join(missing)}")

        need = max(trend_ema, fast_ema, rsi_n, atr_n) + max(
            12, trend_slope_bars + 6, fast_slope_bars + 6, rsi_cross_lookback + 6
        )
        if len(df) < need:
            return Signal(Side.HOLD, 0.0, f"warmup len={len(df)} need>={need}")

        close = df["close"]
        hi = df["high"]
        lo = df["low"]

        e_trend = ema(close, trend_ema)
        e_fast = ema(close, fast_ema)
        rrsi = rsi(close, rsi_n)
        a = atr(df, atr_n)

        if any(x.isna().iloc[-1] for x in (e_trend, e_fast, rrsi, a)):
            return Signal(Side.HOLD, 0.0, "warmup_indicators")

        c1 = float(close.iloc[-1])
        trend1 = float(e_trend.iloc[-1])
        fast1 = float(e_fast.iloc[-1])
        atr1 = float(a.iloc[-1])

        # --- exits / in-position management ---
        if in_position:
            if entry_price is None or entry_index is None:
                return Signal(Side.HOLD, 0.0, "bad_state_missing_entry")

            bars_in_trade = max(0, len(df) - entry_index)

            entry_bar = max(0, entry_index - 1)
            atr_entry = float(a.iloc[entry_bar]) if entry_bar < len(a) else atr1

            init_sl = max(0.0, float(entry_price) - atr_k * atr_entry)
            r_unit = max(1e-9, float(entry_price) - init_sl)

            # trailing from HH since entry using current ATR
            hh = float(hi.iloc[entry_bar:]).max() if entry_bar < len(hi) else float(hi.iloc[-1])
            trail_sl = max(0.0, hh - trail_k * atr1)

            sl = max(init_sl, trail_sl)

            # breakeven lock after +be_r R
            if hh >= float(entry_price) + be_r * r_unit:
                sl = max(sl, float(entry_price))

            tp = float(entry_price) + rr * r_unit

            if bars_in_trade >= max_hold_bars:
                return Signal(Side.SELL, 0.60, "ema_rsi_atr_exit_time", stop_loss=sl, take_profit=tp)

            if bars_in_trade >= min_hold_bars and c1 < trend1 * exit_trend_break:
                return Signal(Side.SELL, 0.62, "ema_rsi_atr_exit_trend_break", stop_loss=sl, take_profit=tp)

            return Signal(Side.HOLD, 0.25, "ema_rsi_atr_hold", stop_loss=sl, take_profit=tp)

        # --- entry gates ---
        if atr1 <= 0:
            return Signal(Side.HOLD, 0.0, "atr_bad")

        if (atr1 / max(1e-9, c1)) < min_atr_pct:
            return Signal(Side.HOLD, 0.0, "atr_pct_low")

        t_prev = float(e_trend.iloc[-(trend_slope_bars + 1)])
        f_prev = float(e_fast.iloc[-(fast_slope_bars + 1)])
        trend_rising = trend1 > t_prev
        fast_rising = fast1 > f_prev

        long_regime = (c1 > trend1) and trend_rising
        above_fast = c1 > fast1

        # must not be extended away from fast EMA (pullback entry)
        ext_atr = (c1 - fast1) / max(1e-9, atr1)
        pullback_ok = (ext_atr <= max_extension_atr) and (ext_atr >= min_pullback_atr)

        r_win = rrsi.iloc[-(rsi_cross_lookback + 1):]
        r_prev = r_win.shift(1)
        cross_hits = (r_prev <= rsi_entry) & (r_win > rsi_entry)
        rsi_cross_recent = bool(cross_hits.fillna(False).any())

        range1 = max(0.0, float(hi.iloc[-1]) - float(lo.iloc[-1]))

        low1 = float(lo.iloc[-1])
        touch_fast = low1 <= (fast1 + 0.15 * atr1)

        impulse_ok = range1 >= impulse_atr * atr1

        if not (long_regime and above_fast and fast_rising and pullback_ok and touch_fast and rsi_cross_recent and impulse_ok):
            return Signal(Side.HOLD, 0.0, "no_setup")

        entry = c1
        init_sl = max(0.0, entry - atr_k * atr1)
        r_unit = max(1e-9, entry - init_sl)
        tp = entry + rr * r_unit

        return Signal(Side.BUY, 0.72, "ema_rsi_atr_buy_pullback", stop_loss=init_sl, take_profit=tp)

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



register("ema_rsi_atr", generate_signal)
