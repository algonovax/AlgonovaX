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
    """
    Generate a trading Signal based on EMA trend, a shorter EMA pullback reclaim, RSI momentum, and ATR-based stop/target.
    
    The function emits:
    - a BUY signal when price is above the trend EMA, reclaims the pullback EMA (price moved from below to above the pull EMA) and RSI crosses above 50; stop loss is set to entry - atr_k * ATR and take profit is entry + rr * (entry - stop).
    - a SELL signal when price crosses below the trend EMA (trend breakdown).
    - a HOLD signal for warmup, missing data, no valid setup, or on error.
    
    Parameters:
        df (pd.DataFrame): Price data containing at minimum 'close', 'high', and 'low' columns.
        trend_ema (int): Lookback length for the trend EMA.
        pullback_ema (int): Lookback length for the pullback (reclaim) EMA.
        rsi_n (int): Period for RSI calculation.
        atr_n (int): Period for ATR calculation.
        atr_k (float): ATR multiplier used to compute the stop loss distance from entry.
        rr (float): Reward-to-risk ratio used to compute take profit from entry and stop.
        min_bars (int | None): Optional override for minimum required bars; if None the function computes a warmup length.
    
    Returns:
        Signal: A Signal object indicating Side.BUY, Side.SELL, or Side.HOLD. For BUY signals the returned object includes stop_loss and take_profit computed from ATR, atr_k, and rr; HOLD reasons include warmup, missing columns, no setup, or error details.
    """
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