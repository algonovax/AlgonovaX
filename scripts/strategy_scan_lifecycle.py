#!/usr/bin/env python3
from __future__ import annotations

import inspect
import os
import sys
from typing import Any, Dict, Optional

from algonovax.data.candles import load_candles_json
from algonovax.strategies import get
from algonovax.strategies.types import Side


def die(msg: str, code: int = 2) -> None:
    print(f"LIFECYCLE_FAIL: {msg}", file=sys.stderr)
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
    allowed = set(sig.parameters.keys())

    env_map = {
        "TREND_EMA": "trend_ema",
        "FAST_EMA": "fast_ema",
        "RSI_N": "rsi_n",
        "RSI_ENTRY": "rsi_entry",
        "ATR_N": "atr_n",
        "ATR_K": "atr_k",
        "TRAIL_K": "trail_k",
        "RR": "rr",
        "IMPULSE_ATR": "impulse_atr",
        "MIN_ATR_PCT": "min_atr_pct",
        "TREND_SLOPE_BARS": "trend_slope_bars",
        "FAST_SLOPE_BARS": "fast_slope_bars",
        "RSI_CROSS_LOOKBACK": "rsi_cross_lookback",
        "MIN_HOLD_BARS": "min_hold_bars",
        "MAX_HOLD_BARS": "max_hold_bars",
        "EXIT_TREND_BREAK": "exit_trend_break",
        "BE_R": "be_r",
        "MAX_EXTENSION_ATR": "max_extension_atr",
        "MIN_PULLBACK_ATR": "min_pullback_atr",
    }

    out: Dict[str, Any] = {}
    used: Dict[str, Any] = {}

    for k, p in env_map.items():
        if p in allowed and (k in os.environ):
            out[p] = _coerce(os.environ[k])
            used[p] = out[p]

    if used:
        print("USED_KWARGS", used)

    return out


def main() -> None:
    path = os.getenv("CANDLES_JSON")
    strat = os.getenv("STRATEGY", "ema_rsi_atr")
    lookback = int(os.getenv("LOOKBACK", "180"))
    use_sl_tp = os.getenv("USE_SL_TP", "0").strip() == "1"

    if not path:
        die("Set CANDLES_JSON=/path/to/candles.json")

    df = load_candles_json(path)
    if df.empty:
        die("Empty df")
    if not {"open", "high", "low", "close"}.issubset(set(df.columns)):
        die(f"Missing columns; have={list(df.columns)}")

    fn = get(strat)
    kwargs = build_kwargs_for(fn)

    start = max(0, len(df) - lookback)

    in_pos = False
    entry_price: Optional[float] = None
    entry_index: Optional[int] = None
    last_sl: Optional[float] = None
    last_tp: Optional[float] = None

    trades = wins = losses = 0

    for i in range(start + 2, len(df) + 1):
        w = df.iloc[:i]
        bar = w.iloc[-1]
        hi = float(bar["high"])
        lo = float(bar["low"])
        close = float(bar["close"])

        sig = fn(
            w,
            in_position=in_pos,
            entry_price=entry_price,
            entry_index=entry_index,
            **kwargs,
        )

        # update dynamic SL/TP from strategy even on HOLD
        if in_pos:
            if sig.stop_loss is not None:
                last_sl = float(sig.stop_loss)
            if sig.take_profit is not None:
                last_tp = float(sig.take_profit)

            if use_sl_tp:
                # intrabar simulation (conservative: SL before TP if both hit)
                if last_sl is not None and lo <= last_sl:
                    pnl = (last_sl - float(entry_price or last_sl))
                    print("EXIT_SL", i, "stop_loss_hit", "fill", last_sl, "entry", entry_price, "pnl", pnl)
                    trades += 1
                    losses += 1 if pnl <= 0 else 0
                    wins += 1 if pnl > 0 else 0
                    in_pos = False
                    entry_price = None
                    entry_index = None
                    last_sl = None
                    last_tp = None
                    continue

                if last_tp is not None and hi >= last_tp:
                    pnl = (last_tp - float(entry_price or last_tp))
                    print("EXIT_TP", i, "take_profit_hit", "fill", last_tp, "entry", entry_price, "pnl", pnl)
                    trades += 1
                    wins += 1 if pnl >= 0 else 0
                    losses += 1 if pnl < 0 else 0
                    in_pos = False
                    entry_price = None
                    entry_index = None
                    last_sl = None
                    last_tp = None
                    continue

            if sig.side == Side.SELL:
                pnl = (close - float(entry_price or close))
                print("EXIT_SELL", i, sig.reason, "close", close, "entry", entry_price, "pnl", pnl)
                trades += 1
                wins += 1 if pnl >= 0 else 0
                losses += 1 if pnl < 0 else 0
                in_pos = False
                entry_price = None
                entry_index = None
                last_sl = None
                last_tp = None
                continue

            continue  # holding

        # not in position
        if sig.side == Side.BUY:
            in_pos = True
            entry_price = close
            entry_index = i
            last_sl = float(sig.stop_loss) if sig.stop_loss is not None else None
            last_tp = float(sig.take_profit) if sig.take_profit is not None else None
            print("BUY", i, sig.reason, "entry", entry_price, "sl", last_sl, "tp", last_tp)

    print(
        "SUMMARY",
        "rows", len(df),
        "lookback", lookback,
        "trades", trades,
        "wins", wins,
        "losses", losses,
        "in_position_end", in_pos,
    )


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass