#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

from algonovax.data.candles import load_candles_json
from algonovax.strategies.indicators import atr, ema, rsi


def die(msg: str, code: int = 2) -> None:
    """
    Print an error message to standard error prefixed with "DIAG_FAIL:" and terminate the process with the given exit code.
    
    Parameters:
        msg (str): Error message to print after the "DIAG_FAIL:" prefix.
        code (int): Exit code to use when terminating the process. Defaults to 2.
    
    Raises:
        SystemExit: Always raised to terminate the program with the specified exit code.
    """
    print(f"DIAG_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    """
    Run diagnostic analysis on candlestick data specified by the CANDLES_JSON environment variable.
    
    Loads candle data, computes EMA (trend and fast), RSI, and ATR with configurable parameters read from environment variables, evaluates a set of gating conditions per rolling window (ATR threshold, trend regime, fast EMA slope, price vs fast EMA, recent RSI cross, and ATR-based impulse), and prints aggregate gate pass counts and the last index where all gates passed. Exits with an error if CANDLES_JSON is not set, the loaded data is empty, or there are not enough rows after warmup.
    
    Environment variables (with defaults):
    - CANDLES_JSON: path to input JSON (required).
    - TREND_EMA (100), FAST_EMA (21), RSI_N (14), RSI_ENTRY (46),
      ATR_N (14), IMPULSE_ATR (0.35), TREND_SLOPE_BARS (6), FAST_SLOPE_BARS (4),
      MIN_ATR_PCT (0.0008), RSI_CROSS_LOOKBACK (8)
    
    Side effects:
    - Prints summary statistics and gate pass counts to standard output.
    - Exits the process on missing/invalid input.
    """
    path = os.getenv("CANDLES_JSON")
    if not path:
        die("Set CANDLES_JSON")

    trend_ema = int(os.getenv("TREND_EMA", "100"))
    fast_ema = int(os.getenv("FAST_EMA", "21"))
    rsi_n = int(os.getenv("RSI_N", "14"))
    rsi_entry = float(os.getenv("RSI_ENTRY", "46"))
    atr_n = int(os.getenv("ATR_N", "14"))
    impulse_atr = float(os.getenv("IMPULSE_ATR", "0.35"))
    trend_slope_bars = int(os.getenv("TREND_SLOPE_BARS", "6"))
    fast_slope_bars = int(os.getenv("FAST_SLOPE_BARS", "4"))
    min_atr_pct = float(os.getenv("MIN_ATR_PCT", "0.0008"))
    rsi_cross_lookback = int(os.getenv("RSI_CROSS_LOOKBACK", "8"))

    df = load_candles_json(path)
    if df.empty:
        die("Empty df")

    close = df["close"]
    hi = df["high"]
    lo = df["low"]

    e_trend = ema(close, trend_ema)
    e_fast = ema(close, fast_ema)
    rr = rsi(close, rsi_n)
    aa = atr(df, atr_n)

    warmup = max(trend_ema, fast_ema, rsi_n, atr_n) + max(
        12, trend_slope_bars + 5, fast_slope_bars + 5, rsi_cross_lookback + 5
    )
    if len(df) <= warmup + 2:
        die(f"Not enough rows after warmup. rows={len(df)} warmup={warmup}")

    start = warmup + 2
    total = 0

    g_atr = g_regime = g_fast = g_above = g_rsi_recent = g_impulse = g_all = 0
    last_good = None

    for i in range(start, len(df) + 1):
        total += 1

        c1 = float(close.iloc[i - 1])

        trend1 = float(e_trend.iloc[i - 1])
        fast1 = float(e_fast.iloc[i - 1])

        trend_prev = float(e_trend.iloc[i - (trend_slope_bars + 1)])
        fast_prev = float(e_fast.iloc[i - (fast_slope_bars + 1)])
        trend_rising = trend1 > trend_prev
        fast_rising = fast1 > fast_prev

        atr1 = float(aa.iloc[i - 1])
        atr_ok = (atr1 > 0.0) and ((atr1 / max(1e-9, c1)) >= min_atr_pct)

        long_regime = (c1 > trend1) and trend_rising
        above_fast = c1 > fast1

        r_window = rr.iloc[i - (rsi_cross_lookback + 1): i]
        r_prev = r_window.shift(1)
        cross_hits = (r_prev <= rsi_entry) & (r_window > rsi_entry)
        rsi_cross_recent = bool(cross_hits.fillna(False).any())

        range1 = max(0.0, float(hi.iloc[i - 1]) - float(lo.iloc[i - 1]))
        impulse_ok = (atr1 > 0.0) and (range1 >= impulse_atr * atr1)

        if atr_ok:
            g_atr += 1
        if long_regime:
            g_regime += 1
        if fast_rising:
            g_fast += 1
        if above_fast:
            g_above += 1
        if rsi_cross_recent:
            g_rsi_recent += 1
        if impulse_ok:
            g_impulse += 1

        ok = atr_ok and impulse_ok and long_regime and above_fast and fast_rising and rsi_cross_recent
        if ok:
            g_all += 1
            last_good = (i, c1, trend1, fast1, atr1, range1)

    print("rows", len(df), "warmup", warmup, "windows_tested", total)
    print(
        "gate_pass_counts:",
        "atr_ok", g_atr,
        "long_regime", g_regime,
        "fast_rising", g_fast,
        "above_fast", g_above,
        "rsi_cross_recent", g_rsi_recent,
        "impulse_ok", g_impulse,
        "ALL", g_all,
    )
    if last_good:
        i, c1, t1, f1, a1, rg = last_good
        print("last_ALL_hit:", "i", i, "close", c1, "trend", t1, "fast", f1, "atr", a1, "range", rg)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass