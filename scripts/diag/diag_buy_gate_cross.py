#!/usr/bin/env python3
import os
import sys

from algonovax.data.candles import load_candles_json
from algonovax.strategies.indicators import ema, rsi


def die(msg: str, code: int = 2) -> None:
    print(f"DIAG_GATE_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main():
    path = os.getenv("CANDLES_JSON")
    if not path:
        die("Set CANDLES_JSON")

    trend_ema_n = int(os.getenv("TREND_EMA", "100"))
    fast_ema_n = int(os.getenv("FAST_EMA", "21"))
    rsi_n = int(os.getenv("RSI_N", "14"))
    rsi_entry = float(os.getenv("RSI_ENTRY", "45"))

    df = load_candles_json(path)
    if df.empty:
        die("Empty df")

    close = df["close"]
    e_trend = ema(close, trend_ema_n)
    e_fast = ema(close, fast_ema_n)
    r = rsi(close, rsi_n)

    w = max(trend_ema_n, fast_ema_n, rsi_n) + 10
    close = close.iloc[w:]
    e_trend = e_trend.iloc[w:]
    e_fast = e_fast.iloc[w:]
    r = r.iloc[w:]
    if len(close) < 10:
        die("Not enough rows after warmup")

    trend_rising = e_trend >= e_trend.shift(3)
    long_regime = (close > e_trend) | (trend_rising & (close > e_trend * 0.998))

    fast_ok = (close >= e_fast) | (
        (close.shift(1) < e_fast.shift(1)) & (close > e_fast)
    )

    rsi_cross_up = (r.shift(1) <= rsi_entry) & (r > rsi_entry)

    both = long_regime & fast_ok
    all3 = both & rsi_cross_up

    print("rows_after_warmup", len(close))
    print("rsi_entry", rsi_entry)
    print("count_long_regime", int(long_regime.sum()))
    print("count_fast_ok", int(fast_ok.sum()))
    print("count_both_long_fast", int(both.sum()))
    print("count_rsi_cross_up", int(rsi_cross_up.sum()))
    print("count_all3_buy_gate", int(all3.sum()))

    if int(all3.sum()) > 0:
        idx = all3[all3].index[:10]
        for i in idx:
            print(
                "BUY_GATE_AT_INDEX",
                int(i),
                "close",
                float(close.loc[i]),
                "rsi",
                float(r.loc[i]),
            )

    # show best candidate if none
    if int(all3.sum()) == 0:
        # how close does r get to entry when both gates are true?
        r_both = r[both]
        if len(r_both) == 0:
            print("NOTE: never both long_regime & fast_ok true")
        else:
            best = float((r_both - rsi_entry).max())
            print("max_rsi_minus_entry_when_long_fast_true", best)


if __name__ == "__main__":
    main()
