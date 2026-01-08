#!/usr/bin/env python3
import os
import sys
import pandas as pd

from algonovax.data.candles import load_candles_json
from algonovax.strategies.indicators import ema, rsi


def die(msg: str, code: int = 2) -> None:
    """
    Print a diagnostic failure message to stderr and terminate the process with the given exit code.
    
    Parameters:
        msg (str): Message to include in the diagnostic failure output.
        code (int): Exit code to terminate the process with (default 2).
    """
    print(f"DIAG_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main():
    """
    Run the diagnostic analysis: load candles, compute EMAs and RSI, evaluate buy gates, and print summary metrics.
    
    Reads the path from the CANDLES_JSON environment variable and other optional environment settings (TREND_EMA, FAST_EMA, RSI_N, RSI_BUY). Loads candle data, computes trend and fast EMAs and RSI, discards an initial warmup period, validates remaining rows, then computes RSI statistics, gate indicators (long_regime, rsi_rebound, fast_ok), aggregate counts, combinations, and closest misses; prints these metrics to stdout. Exits the process via die(...) if required environment variables are missing, the data is empty, or there are too few rows after warmup.
    """
    path = os.getenv("CANDLES_JSON")
    if not path:
        die("Set CANDLES_JSON")

    trend_ema_n = int(os.getenv("TREND_EMA", "100"))
    fast_ema_n = int(os.getenv("FAST_EMA", "21"))
    rsi_n = int(os.getenv("RSI_N", "14"))
    rsi_buy = float(os.getenv("RSI_BUY", "42"))

    df = load_candles_json(path)
    if df.empty:
        die("Empty df")

    close = df["close"]
    e_trend = ema(close, trend_ema_n)
    e_fast = ema(close, fast_ema_n)
    r = rsi(close, rsi_n)

    # ignore warmup
    w = max(trend_ema_n, fast_ema_n, rsi_n) + 5
    df = df.iloc[w:].copy()
    e_trend = e_trend.iloc[w:]
    e_fast = e_fast.iloc[w:]
    r = r.iloc[w:]
    close = close.iloc[w:]

    if len(df) < 5:
        die("Not enough rows after warmup")

    # metrics
    rmin = float(pd.to_numeric(r, errors="coerce").min())
    rmax = float(pd.to_numeric(r, errors="coerce").max())
    below = int((r < rsi_buy).sum())

    # your buy gates
    trend_rising = (e_trend >= e_trend.shift(3))
    long_regime = (close > e_trend) | (trend_rising & (close > e_trend * 0.998))

    rsi_rebound = (r.shift(1) < rsi_buy) & (r > r.shift(1))
    fast_ok = (close >= e_fast) | ((close.shift(1) < e_fast.shift(1)) & (close > e_fast))

    combos = pd.DataFrame({
        "long_regime": long_regime.astype(int),
        "rsi_rebound": rsi_rebound.astype(int),
        "fast_ok": fast_ok.astype(int),
    })

    print("rows_after_warmup", len(df))
    print("rsi_min", rmin)
    print("rsi_max", rmax)
    print("rsi_below_buy_count", below)

    print("gate_counts",
          "long_regime", int(combos["long_regime"].sum()),
          "rsi_rebound", int(combos["rsi_rebound"].sum()),
          "fast_ok", int(combos["fast_ok"].sum()),
    )

    all3 = int(((combos["long_regime"] == 1) & (combos["rsi_rebound"] == 1) & (combos["fast_ok"] == 1)).sum())
    print("all_3_gates_true", all3)

    # show closest misses: long+fast but RSI rebound missing
    miss = combos[(combos["long_regime"] == 1) & (combos["fast_ok"] == 1) & (combos["rsi_rebound"] == 0)]
    print("miss_long_fast_only", len(miss))


if __name__ == "__main__":
    main()