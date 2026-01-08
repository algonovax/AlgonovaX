#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
OUT_REPORT = ROOT / "data" / "backtest_report.json"
OUT_TRADES = ROOT / "data" / "backtest_trades.json"

# Candle rows: [ts_ms, open, high, low, close, vol]
def load_candles(path: Path) -> List[List[float]]:
    """
    Load candle rows from a JSON file.
    
    Supports two formats: either the JSON is a list of candle rows or a dict containing a "candles" key whose value is the list. Each candle row is expected to be a list of numeric values (e.g., [ts, open, high, low, close, ...]).
    
    Parameters:
        path (Path): Path to the JSON file to read.
    
    Returns:
        List[List[float]]: The list of candle rows.
    
    Raises:
        ValueError: If the parsed JSON is not a non-empty list of candles.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "candles" in data:
        data = data["candles"]
    if not isinstance(data, list) or not data:
        raise ValueError("bad candle json")
    return data


def max_drawdown(equity: List[float]) -> Tuple[float, float]:
    """
    Compute the maximum drawdown from a time-ordered equity series.
    
    Parameters:
        equity (List[float]): Sequence of equity values (account value) over time.
    
    Returns:
        Tuple[float, float]: A pair (max_drawdown, max_drawdown_pct) where
            - max_drawdown is the largest peak-to-trough drop in absolute units,
            - max_drawdown_pct is the same drop expressed as a fraction of the peak (0.0–1.0).
    """
    if not equity:
        return 0.0, 0.0
    peak = float(equity[0])
    max_dd = 0.0
    for x in equity:
        x = float(x)
        if x > peak:
            peak = x
        dd = peak - x
        if dd > max_dd:
            max_dd = dd
    max_dd_pct = (max_dd / peak) if peak > 0 else 0.0
    return float(max_dd), float(max_dd_pct)

def senv(k: str, d: str) -> str:
    """
    Return the value of an environment variable or a default when missing or empty.
    
    Parameters:
        k (str): Name of the environment variable to read.
        d (str): Default string to return if the variable is not set or is empty (after stripping).
    
    Returns:
        str: The stripped environment variable value if present and non-empty, otherwise `d`.
    """
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else v.strip()

def ienv(k: str, d: int) -> int:
    """
    Read an environment variable and convert it to an integer, returning a default when missing or empty.
    
    Parameters:
        k (str): Environment variable name to read.
        d (int): Default integer to return if the environment variable is unset or an empty string.
    
    Returns:
        int: The integer value of the environment variable, or `d` if the variable is not present or is empty.
    """
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else int(v)

def fenv(k: str, d: float) -> float:
    """
    Read an environment variable, parse it as a float, and return it or a default.
    
    Parameters:
        k (str): Environment variable name to read.
        d (float): Default value returned if the variable is missing or is empty/whitespace.
    
    Returns:
        float: The parsed float value of the environment variable, or `d` if the variable is missing or contains only whitespace.
    """
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else float(v)

def clamp_window(candles: List[List[float]], start_ms: int, end_ms: int) -> List[List[float]]:
    """
    Filter candle rows to a time window defined by millisecond timestamps.
    
    Only rows whose first element (timestamp in milliseconds) falls within the inclusive range [start_ms, end_ms] are retained. If start_ms or end_ms is non-positive, that bound is ignored; if both are non-positive the input list is returned unchanged.
    
    Parameters:
        candles (List[List[float]]): Sequence of candle rows where each row's first element is the timestamp in milliseconds.
        start_ms (int): Lower timestamp bound in milliseconds; values <= 0 disable the lower bound.
        end_ms (int): Upper timestamp bound in milliseconds; values <= 0 disable the upper bound.
    
    Returns:
        List[List[float]]: Filtered list of candle rows satisfying the provided time bounds.
    """
    if start_ms <= 0 and end_ms <= 0:
        return candles
    out = []
    for r in candles:
        ts = int(r[0])
        if start_ms and ts < start_ms:
            continue
        if end_ms and ts > end_ms:
            continue
        out.append(r)
    return out

def rolling_max(vals: List[float], n: int, idx: int) -> float:
    """
    Get the maximum value over the lookback window of up to `n` elements ending before `idx`.
    
    Parameters:
    	vals (List[float]): Sequence of numeric values.
    	n (int): Lookback window size.
    	idx (int): Current index; the window is vals[max(0, idx-n):idx].
    
    Returns:
    	max_value (float): The maximum of the lookback window if it is non-empty, otherwise `vals[idx]`.
    """
    a = max(0, idx - n)
    return max(vals[a:idx]) if idx > a else vals[idx]

def rolling_min(vals: List[float], n: int, idx: int) -> float:
    """
    Get the minimum value in the lookback window that ends at index `idx`.
    
    Parameters:
    	vals (List[float]): Sequence of values to inspect.
    	n (int): Lookback window size (number of prior elements to consider).
    	idx (int): Current index (0-based); the window is vals[max(0, idx-n) : idx].
    
    Returns:
    	The minimum value over the window vals[max(0, idx-n) : idx], or vals[idx] if that window is empty.
    """
    a = max(0, idx - n)
    return min(vals[a:idx]) if idx > a else vals[idx]

@dataclass
class Trade:
    entry_ts: int
    entry_px: float
    exit_ts: int
    exit_px: float
    qty: float
    pnl: float

def main() -> int:
    """
    Run a Donchian breakout backtest using candle data from an environment-specified file and write a summary report and trades file.
    
    Reads configuration from environment variables (including CANDLE_FILE, windowing, fees, stake, and strategy parameters), loads and optionally windows candle data, runs a simple ATR-based Donchian breakout strategy that enters longs and exits on ATR stop, take-profit, or maximum hold time, and accumulates trade and equity results. Writes a JSON summary report and a detailed trades JSON to configured output paths.
    
    Returns:
        int: Exit code where `0` indicates success and `2` indicates an error (an error report is written on failure).
    """
    try:
        candle_file = senv("CANDLE_FILE", "")
        if not candle_file:
            raise ValueError("CANDLE_FILE env missing")
        candles = load_candles(Path(candle_file))

        start_ms = int(senv("START_MS", "0"))
        end_ms = int(senv("END_MS", "0"))
        candles = clamp_window(candles, start_ms, end_ms)

        min_candles = ienv("MIN_CANDLES", 1)
        if len(candles) < min_candles:
            raise ValueError(f"not enough candles: {len(candles)} < {min_candles}")

        fee_rate = fenv("FEE_RATE", 0.001)
        slip_rate = fenv("SLIPPAGE_RATE", 0.0003)
        stake_quote = fenv("STAKE_QUOTE", 100.0)

        # Tunable params (candidate knobs)
        DONCHIAN_N = ienv("DONCHIAN_N", 20)           # breakout lookback
        ATR_N = ienv("ATR_N", 14)                     # for stop
        STOP_K = fenv("STOP_K", 2.0)                  # stop distance in ATR
        TAKE_K = fenv("TAKE_K", 3.0)                  # takeprofit distance in ATR
        MAX_HOLD = ienv("MAX_HOLD_BARS", 96)          # bars

        ts = [int(r[0]) for r in candles]
        high = [float(r[2]) for r in candles]
        low = [float(r[3]) for r in candles]
        close = [float(r[4]) for r in candles]

        # ATR (simple)
        tr: List[float] = []
        for i in range(len(candles)):
            if i == 0:
                tr.append(high[i] - low[i])
            else:
                tr.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))
        atr: List[float] = [0.0] * len(candles)
        for i in range(len(candles)):
            a = max(0, i-ATR_N+1)
            w = tr[a:i+1]
            atr[i] = sum(w)/len(w) if w else 0.0

        trades: List[Trade] = []
        cum_pnl = 0.0
        equity: List[float] = [float(stake_quote)]
        in_pos = False
        entry_i = -1
        entry_px = 0.0
        qty = 0.0
        stop_px = 0.0
        take_px = 0.0

        for i in range(1, len(candles)):
            if i < max(DONCHIAN_N, ATR_N) + 1:
                continue

            if not in_pos:
                # breakout above prior donchian high
                dh = rolling_max(high, DONCHIAN_N, i)
                if close[i] > dh:
                    # buy at close with slippage + fees
                    px = close[i] * (1.0 + slip_rate)
                    qty = (stake_quote / px) * (1.0 - fee_rate)
                    entry_px = px
                    entry_i = i
                    a = atr[i]
                    stop_px = entry_px - STOP_K * a
                    take_px = entry_px + TAKE_K * a
                    in_pos = True
            else:
                # exit conditions
                hold = i - entry_i
                px_mid = close[i]
                # simulate worst-case slippage on exit
                exit_px = px_mid * (1.0 - slip_rate)

                hit_stop = low[i] <= stop_px
                hit_take = high[i] >= take_px
                time_exit = hold >= MAX_HOLD

                if hit_stop:
                    exit_px = stop_px * (1.0 - slip_rate)
                elif hit_take:
                    exit_px = take_px * (1.0 - slip_rate)

                if hit_stop or hit_take or time_exit:
                    proceeds = qty * exit_px * (1.0 - fee_rate)
                    cost = stake_quote
                    pnl = proceeds - cost
                    cum_pnl += float(pnl)
                    equity.append(float(stake_quote) + float(cum_pnl))
                    trades.append(
                        Trade(
                            entry_ts=ts[entry_i],
                            entry_px=entry_px,
                            exit_ts=ts[i],
                            exit_px=exit_px,
                            qty=qty,
                            pnl=pnl,
                        )
                    )
                    in_pos = False
                    entry_i = -1

        pnl = sum(t.pnl for t in trades)
        wins = sum(1 for t in trades if t.pnl > 0)
        losses = sum(1 for t in trades if t.pnl <= 0)
        trades_n = len(trades)
        max_dd, max_dd_pct = max_drawdown(equity)

        pnl_pct = (pnl / stake_quote) * 100.0 if stake_quote else 0.0

        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_TRADES.parent.mkdir(parents=True, exist_ok=True)

        report: dict[str, Any] = {
            "candle_file": candle_file,
            "candles": len(candles),
            "trades": trades_n,
            "wins": wins,
            "losses": losses,
            "pnl": float(pnl),
          "max_dd": max_dd,
          "max_dd_pct": max_dd_pct,
            "pnl_pct": float(pnl_pct),
            "params": {
                "DONCHIAN_N": DONCHIAN_N,
                "ATR_N": ATR_N,
                "STOP_K": STOP_K,
                "TAKE_K": TAKE_K,
                "MAX_HOLD_BARS": MAX_HOLD,
            },
            "costs": {
                "fee_rate": fee_rate,
                "slippage_rate": slip_rate,
                "stake_quote": stake_quote,
            },
        }
        OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        OUT_TRADES.write_text(
            json.dumps([t.__dict__ for t in trades], indent=2),
            encoding="utf-8",
        )
        return 0

    except Exception as e:
        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_REPORT.write_text(json.dumps({"error": str(e)}, indent=2), encoding="utf-8")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())