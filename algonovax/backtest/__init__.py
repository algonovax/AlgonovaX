from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Tuple, Dict, Optional

import math

try:
    import pandas as pd
except Exception as e:
    raise RuntimeError("pandas is required for backtest engine (strategy uses ewm). Install pandas.") from e


@dataclass
class Trade:
    entry_ts: int
    exit_ts: int
    entry_px: float
    exit_px: float
    qty: float
    pnl_quote: float
    reason: str


def to_jsonable(x: Any) -> Any:
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, dict):
        return {k: to_jsonable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [to_jsonable(v) for v in x]
    if hasattr(x, "__dict__"):
        return {k: to_jsonable(v) for k, v in x.__dict__.items()}
    return str(x)


def load_ohlcv_json(path) -> List[List[float]]:
    import json
    from pathlib import Path as _P
    p = _P(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    # Expect rows: [ts_ms, open, high, low, close, volume]
    if not isinstance(obj, list) or not obj:
        raise ValueError(f"Invalid candles json: {p}")
    return obj


def _as_series(xs: Any) -> "pd.Series":
    if isinstance(xs, pd.Series):
        return xs
    return pd.Series(list(xs), dtype="float64")


def _normalize_signal(sig: Any, n: int) -> List[int]:
    """
    Normalize strategy output into a list[int] length n with:
      1 => long entry signal
      0 => no entry
    Supports:
      - list/tuple of ints/bools
      - pandas Series
      - objects with .side/.signal/.values/.to_list
      - enums Side with values like 'LONG'/'BUY'/1
    """
    try:
        import pandas as pd  # local
    except Exception:
        pd = None

    def to_int(v: Any) -> int:
        if v is None:
            return 0
        if isinstance(v, (int, bool)):
            return 1 if int(v) != 0 else 0
        s = str(v).upper()
        if "LONG" in s or "BUY" in s:
            return 1
        # if enum-like numeric
        try:
            iv = int(v)
            return 1 if iv != 0 else 0
        except Exception:
            return 0

    # direct list-like
    if isinstance(sig, (list, tuple)):
        out = [to_int(v) for v in sig]
        return (out + [0] * max(0, n - len(out)))[:n]

    # pandas series
    if pd is not None and isinstance(sig, pd.Series):
        out = [to_int(v) for v in sig.tolist()]
        return (out + [0] * max(0, n - len(out)))[:n]

    # common attributes
    for attr in ("side", "signal", "values", "sides"):
        if hasattr(sig, attr):
            v = getattr(sig, attr)
            return _normalize_signal(v, n)

    # method
    for meth in ("to_list", "tolist"):
        if hasattr(sig, meth):
            try:
                v = getattr(sig, meth)()
                return _normalize_signal(v, n)
            except Exception:
                pass

    # last resort: single scalar means "latest only"
    return [0] * (n - 1) + [to_int(sig)]


def run_backtest_atr_exits(
    candles: List[List[float]],
    symbol: str,
    timeframe: str,
    strategy: Callable[[Any, Any, Any], Any],
    atr_value: Callable[[Any, Any, Any], Any],
    fee_rate: float,
    slippage_rate: float,
    stake_quote: float,
    stop_atr_mult: float,
    tp_atr_mult: float,
    min_hold_bars: int,
    cooldown_bars: int,
) -> Tuple[Dict[str, Any], List[Trade]]:
    """
    Long-only backtest:
      - enter on signal==1 at close*(1+slippage)
      - exit on stop (low<=stop) or takeprofit (high>=tp)
      - fees applied on notional at entry and exit: fee_rate*(entry_notional+exit_notional)
      - cooldown after exit
    """
    if not candles:
        raise ValueError("No candles")

    ts = [int(r[0]) for r in candles]
    highs = _as_series([float(r[2]) for r in candles])
    lows  = _as_series([float(r[3]) for r in candles])
    closes= _as_series([float(r[4]) for r in candles])

    n = len(candles)

    sig_raw = strategy(highs, lows, closes)
    sig = _normalize_signal(sig_raw, n)

    atr_raw = atr_value(highs, lows, closes)
    atr = _as_series(atr_raw)

    in_pos = False
    entry_i = -1
    entry_px = 0.0
    qty = 0.0
    stop = 0.0
    tp = 0.0
    cooldown = 0

    equity = 0.0
    peak = 0.0
    max_dd = 0.0

    trades: List[Trade] = []

    for i in range(n):
        if cooldown > 0:
            cooldown -= 1

        if not in_pos:
            if cooldown == 0 and sig[i] == 1:
                px = float(closes.iat[i]) * (1.0 + slippage_rate)
                if px <= 0:
                    continue
                qty = stake_quote / px
                entry_px = px
                entry_i = i

                a = float(atr.iat[i]) if i < len(atr) else 0.0
                if not math.isfinite(a) or a <= 0:
                    # cannot size stops without ATR
                    continue
                stop = entry_px - stop_atr_mult * a
                tp = entry_px + tp_atr_mult * a

                in_pos = True
            continue

        # in position
        hold = i - entry_i
        if hold < max(0, int(min_hold_bars)):
            continue

        lo = float(lows.iat[i])
        hi = float(highs.iat[i])

        exit_reason: Optional[str] = None
        exit_px: Optional[float] = None

        # conservative ordering: if both hit same bar, assume stop first
        if lo <= stop:
            exit_reason = "STOP"
            exit_px = stop * (1.0 - slippage_rate)
        elif hi >= tp:
            exit_reason = "TP"
            exit_px = tp * (1.0 - slippage_rate)

        if exit_reason and exit_px and exit_px > 0:
            entry_notional = qty * entry_px
            exit_notional = qty * exit_px
            fees = fee_rate * (entry_notional + exit_notional)
            pnl = (exit_notional - entry_notional) - fees

            equity += pnl
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)

            trades.append(Trade(
                entry_ts=ts[entry_i],
                exit_ts=ts[i],
                entry_px=float(entry_px),
                exit_px=float(exit_px),
                qty=float(qty),
                pnl_quote=float(pnl),
                reason=exit_reason,
            ))

            in_pos = False
            entry_i = -1
            entry_px = 0.0
            qty = 0.0
            stop = 0.0
            tp = 0.0
            cooldown = int(cooldown_bars)

    wins = sum(1 for t in trades if t.pnl_quote > 0)
    losses = sum(1 for t in trades if t.pnl_quote <= 0)

    report = {
        "symbol": symbol,
        "timeframe": timeframe,
        "start_ts": ts[0],
        "end_ts": ts[-1],
        "trades": len(trades),
        "wins": wins,
        "losses": losses,
        "net_pnl_quote": float(sum(t.pnl_quote for t in trades)),
        "max_drawdown_quote": float(max_dd),
    }
    return report, trades
