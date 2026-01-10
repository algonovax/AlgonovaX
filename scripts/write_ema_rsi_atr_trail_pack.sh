#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

on_err() {
  local ec=$?
  echo "PACK_CRASH exit_code=$ec line=${BASH_LINENO[0]} cmd=${BASH_COMMAND}" >&2
  exit "$ec"
}
trap on_err ERR

# --- ema_rsi_atr with ATR trailing stop + time stop; strategy returns dynamic SL/TP while in position ---
cat > algonovax/strategies/ema_rsi_atr.py <<'PY'
from __future__ import annotations

import pandas as pd

from .indicators import atr, ema, rsi
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
    impulse_atr: float = 0.35,        # range >= impulse_atr * ATR
    min_atr_pct: float = 0.0008,      # ATR/close >= this
    trend_slope_bars: int = 6,        # trend EMA rising over this window
    fast_slope_bars: int = 4,         # fast EMA rising over this window
    rsi_cross_lookback: int = 8,      # RSI cross can be recent within this window
    # --- risk/exit model ---
    atr_k: float = 2.2,               # initial stop distance in ATR
    trail_k: float = 2.0,             # trailing stop distance in ATR (from highest high since entry)
    rr: float = 1.5,                  # TP = entry + rr * (entry - initial_sl)
    min_hold_bars: int = 6,           # don’t churn
    max_hold_bars: int = 72,          # time stop (5m*72=6h)
    exit_trend_break: float = 0.997,  # hard regime break: close < trend * this
) -> Signal:
    try:
        if df is None or df.empty:
            return Signal(Side.HOLD, 0.0, "empty_df")

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

            # bars since entry (entry_index is df length at entry time)
            bars_in_trade = max(0, len(df) - entry_index)

            # initial stop based on ATR at entry bar
            entry_bar = max(0, entry_index - 1)
            atr_entry = float(a.iloc[entry_bar]) if entry_bar < len(a) else atr1
            init_sl = max(0.0, float(entry_price) - atr_k * atr_entry)

            # trailing stop from highest high since entry using current ATR
            hh = float(hi.iloc[entry_bar:].max()) if entry_bar < len(hi) else float(hi.iloc[-1])
            trail_sl = max(0.0, hh - trail_k * atr1)
            sl = max(init_sl, trail_sl)

            tp = float(entry_price) + rr * (float(entry_price) - init_sl)

            # time stop / hard regime break only (scanner will simulate SL/TP intrabar)
            if bars_in_trade >= max_hold_bars:
                return Signal(Side.SELL, 0.60, "ema_rsi_atr_exit_time", stop_loss=sl, take_profit=tp)

            if bars_in_trade >= min_hold_bars and c1 < trend1 * exit_trend_break:
                return Signal(Side.SELL, 0.62, "ema_rsi_atr_exit_trend_break", stop_loss=sl, take_profit=tp)

            # keep holding, but provide dynamic SL/TP for scanner
            return Signal(Side.HOLD, 0.25, "ema_rsi_atr_hold", stop_loss=sl, take_profit=tp)

        # --- entry gates ---
        if atr1 <= 0:
            return Signal(Side.HOLD, 0.0, "atr_bad")

        atr_ok = (atr1 / max(1e-9, c1)) >= min_atr_pct
        if not atr_ok:
            return Signal(Side.HOLD, 0.0, "atr_pct_low")

        # slopes
        t_prev = float(e_trend.iloc[-(trend_slope_bars + 1)])
        f_prev = float(e_fast.iloc[-(fast_slope_bars + 1)])
        trend_rising = trend1 > t_prev
        fast_rising = fast1 > f_prev

        long_regime = (c1 > trend1) and trend_rising
        above_fast = c1 > fast1

        # RSI cross recent
        r_win = rrsi.iloc[-(rsi_cross_lookback + 1):]
        r_prev = r_win.shift(1)
        cross_hits = (r_prev <= rsi_entry) & (r_win > rsi_entry)
        rsi_cross_recent = bool(cross_hits.fillna(False).any())

        # impulse
        range1 = max(0.0, float(hi.iloc[-1]) - float(lo.iloc[-1]))
        impulse_ok = range1 >= impulse_atr * atr1

        if not (long_regime and above_fast and fast_rising and rsi_cross_recent and impulse_ok):
            return Signal(Side.HOLD, 0.0, "no_setup")

        entry = c1
        init_sl = max(0.0, entry - atr_k * atr1)
        tp = entry + rr * (entry - init_sl)

        return Signal(Side.BUY, 0.72, "ema_rsi_atr_buy_trail", stop_loss=init_sl, take_profit=tp)

    except Exception as e:
        return Signal(Side.HOLD, 0.0, f"error:{type(e).__name__}")


register("ema_rsi_atr", generate_signal)
PY

# --- lifecycle scanner: simulates intrabar SL/TP using high/low; passes entry_index; tracks wins/losses ---
cat > scripts/strategy_scan_lifecycle.py <<'PY'
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
PY

chmod +x scripts/strategy_scan_lifecycle.py

python -m py_compile algonovax/strategies/ema_rsi_atr.py scripts/strategy_scan_lifecycle.py
echo "OK: wrote ema_rsi_atr trail pack + py_compile passed"
