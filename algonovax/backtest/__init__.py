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
    """
    Convert an arbitrary Python object into a JSON-serializable form.
    
    Parameters:
        x (Any): The value to convert.
    
    Returns:
        Any: A JSON-serializable representation of `x`. Primitive types (str, int, float, bool, None) are returned unchanged; dicts and lists are converted recursively; objects with a `__dict__` are converted to a dict of their attributes (recursively); all other values are converted to their string representation.
    """
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
    """
    Load OHLCV candle data from a JSON file.
    
    Parameters:
        path (str | os.PathLike): File path to a JSON file containing a non-empty list of candle rows.
    
    Returns:
        List[List[float]]: List of candles where each row is expected to be
        [timestamp_ms, open, high, low, close, volume].
    
    Raises:
        ValueError: If the file does not contain a non-empty JSON list of candles.
    """
    import json
    from pathlib import Path as _P
    p = _P(path)
    obj = json.loads(p.read_text(encoding="utf-8"))
    # Expect rows: [ts_ms, open, high, low, close, volume]
    if not isinstance(obj, list) or not obj:
        raise ValueError(f"Invalid candles json: {p}")
    return obj


def _as_series(xs: Any) -> "pd.Series":
    """
    Coerce the input into a pandas Series with dtype float64.
    
    Parameters:
        xs (Any): A pandas Series or any sequence/iterable of numeric-like values.
    
    Returns:
        pd.Series: The input as a pandas Series with dtype float64; if `xs` is already a Series it is returned unchanged.
    """
    if isinstance(xs, pd.Series):
        return xs
    return pd.Series(list(xs), dtype="float64")


def _normalize_signal(sig: Any, n: int) -> List[int]:
    """
    Normalize various strategy signal representations into a list of entry flags.
    
    Accepts lists/tuples, pandas Series, objects exposing attributes named 'side', 'signal', 'values', or 'sides', objects with `to_list`/`tolist` methods, or a scalar (interpreted as a signal for the latest index only). Values that are non-zero integers/bools or strings containing "LONG" or "BUY" are treated as entry signals.
    
    Parameters:
        sig (Any): Strategy output in one of the supported forms.
        n (int): Desired length of the output list; results are padded with zeros or truncated to this length.
    
    Returns:
        List[int]: Length `n` list where `1` indicates a long entry signal and `0` indicates no entry.
    """
    try:
        import pandas as pd  # local
    except Exception:
        pd = None

    def to_int(v: Any) -> int:
        """
        Determine whether an arbitrary value represents a long/buy signal.
        
        Interprets the input as a signal candidate and returns 1 for a long/buy signal or 0 otherwise. Recognizes common representations such as booleans/integers (non-zero), textual indicators containing "LONG" or "BUY", and numeric-like values.
        
        Parameters:
        	v (Any): Value to interpret as a trading signal.
        
        Returns:
        	int: `1` if `v` represents a long/buy signal, `0` otherwise.
        """
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
    Run a long-only backtest using ATR-based stops and take-profits.
    
    Parameters:
        candles (List[List[float]]): OHLCV rows as [ts_ms, open, high, low, close, volume].
        symbol (str): Instrument identifier for the report.
        timeframe (str): Timeframe identifier for the report.
        strategy (Callable[[Any, Any, Any], Any]): Function producing entry signals from (highs, lows, closes). Its output may be a list/series/scalar and will be normalized so that `1` means enter long at that bar.
        atr_value (Callable[[Any, Any, Any], Any]): Function producing ATR-like values from (highs, lows, closes); values must be positive and are used to size the stop and take-profit distances.
        fee_rate (float): Proportional fee applied to traded notional at entry and exit (e.g., 0.001 = 0.1%).
        slippage_rate (float): Proportional execution slippage applied to entry and exit prices (e.g., 0.001 = 0.1%).
        stake_quote (float): Quote-currency amount allocated per trade to size the position (qty = stake_quote / entry_price).
        stop_atr_mult (float): Multiplier of ATR subtracted from entry price to compute the stop level.
        tp_atr_mult (float): Multiplier of ATR added to entry price to compute the take-profit level.
        min_hold_bars (int): Minimum number of bars to hold a position before allowing exits.
        cooldown_bars (int): Number of bars to wait after an exit before entering a new trade.
    
    Returns:
        Tuple[Dict[str, Any], List[Trade]]: A tuple where the first element is a report dictionary containing summary metrics
        ("symbol", "timeframe", "start_ts", "end_ts", "trades", "wins", "losses", "net_pnl_quote", "max_drawdown_quote"),
        and the second element is the list of executed Trade records (entry/exit timestamps, prices, quantity, pnl, and reason).
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