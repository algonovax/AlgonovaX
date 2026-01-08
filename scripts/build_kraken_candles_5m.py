#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "candles"


def senv(name: str, default: str) -> str:
    """
    Retrieve an environment variable's trimmed value or return a default when it is missing or blank.
    
    Parameters:
        name (str): The environment variable name to read.
        default (str): The fallback value returned when the environment variable is not set or is empty/whitespace.
    
    Returns:
        value (str): The environment variable's value with surrounding whitespace removed, or `default` if the variable is missing or blank.
    """
    v = os.environ.get(name)
    return default if v is None or v.strip() == "" else v.strip()


def ienv(name: str, default: int) -> int:
    """
    Get an environment variable by name and return its integer value, falling back to `default` when the variable is missing or empty.
    
    Parameters:
        name (str): Environment variable name to read.
        default (int): Value to return when the variable is not set or is blank.
    
    Returns:
        int: The integer parsed from the environment variable, or `default` if the variable is missing or empty.
    
    Raises:
        ValueError: If the environment variable is present but cannot be converted to an integer.
    """
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return int(v)


def symbol_to_fs(symbol: str) -> str:
    """
    Convert a trading symbol into a filesystem-friendly string.
    
    Parameters:
        symbol (str): Trading symbol (e.g., "btc/usd" or "BTC-USD").
    
    Returns:
        str: The input symbol with '/' and '-' replaced by '_' and converted to upper case (e.g., "BTC_USD").
    """
    return symbol.replace("/", "_").replace("-", "_").upper()


def parse_trade(t: Any) -> Tuple[int, float, float]:
    """
    Normalize a trade record into a (timestamp, price, volume) triple.
    
    Accepts either a sequence (list/tuple with at least three elements) where the
    first three entries are timestamp, price, and volume, or a mapping with keys
    for timestamp ("timestamp", "time", "ts", "t"), price ("price", "p"), and
    volume ("amount", "volume", "qty", "v"). If volume is missing in a mapping,
    it defaults to 0.0.
    
    Parameters:
        t (Any): Trade data as a sequence or mapping.
    
    Returns:
        Tuple[int, float, float]: (timestamp_ms, price, volume) with timestamp
        converted to int and price/volume converted to float.
    
    Raises:
        ValueError: If a mapping is missing a timestamp or price.
        TypeError: If the input is neither a supported sequence nor mapping.
    """
    if isinstance(t, (list, tuple)) and len(t) >= 3:
        return int(t[0]), float(t[1]), float(t[2])

    if isinstance(t, dict):
        ts = t.get("timestamp") or t.get("time") or t.get("ts") or t.get("t")
        if ts is None:
            raise ValueError("trade missing timestamp")
        price = t.get("price") or t.get("p")
        if price is None:
            raise ValueError("trade missing price")
        vol = t.get("amount") or t.get("volume") or t.get("qty") or t.get("v")
        if vol is None:
            vol = 0.0
        return int(ts), float(price), float(vol)

    raise TypeError(f"Unknown trade type: {type(t)}")


def floor_ts(ts_ms: int, tf_ms: int) -> int:
    """
    Floor a millisecond timestamp down to the nearest multiple of a timeframe.
    
    Parameters:
    	ts_ms (int): Timestamp in milliseconds to be floored.
    	tf_ms (int): Timeframe length in milliseconds used as the bucket size.
    
    Returns:
    	floored_ts (int): The largest multiple of `tf_ms` that is less than or equal to `ts_ms`, expressed in milliseconds.
    """
    return (ts_ms // tf_ms) * tf_ms


def build_ohlcv(trades: List[Any], timeframe_ms: int) -> List[List[float]]:
    """
    Aggregate a sequence of trades into time-bucketed OHLCV candles.
    
    Parameters:
        trades (List[Any]): Sequence of trade records. Each trade must provide a timestamp, a price, and a volume.
        timeframe_ms (int): Timeframe length in milliseconds used to bucket trades.
    
    Returns:
        List[List[float]]: Ordered list of candles, each formatted as
            [bucket_start_ts, open, high, low, close, volume]
            where `bucket_start_ts` is an integer timestamp (ms) for the bucket start and the remaining values are floats.
    """
    buckets: Dict[int, List[Tuple[int, float, float]]] = {}

    for tr in trades:
        ts, price, vol = parse_trade(tr)
        b = floor_ts(ts, timeframe_ms)
        buckets.setdefault(b, []).append((ts, price, vol))

    out: List[List[float]] = []
    for b in sorted(buckets.keys()):
        rows = sorted(buckets[b], key=lambda x: x[0])
        o = rows[0][1]
        c = rows[-1][1]
        h = max(r[1] for r in rows)
        l = min(r[1] for r in rows)
        v = sum(r[2] for r in rows)
        out.append([int(b), float(o), float(h), float(l), float(c), float(v)])

    return out


def main() -> int:
    """
    Build OHLCV candles from a trades JSON file and write them to the data/candles directory.
    
    Reads configuration from environment (TRADES_FILE required; EXCHANGE, SYMBOL, TIMEFRAME, TF_MS optional), loads trades from the specified JSON (either a top-level list or a dict containing a list under "trades", "data", or "result"), validates there are at least 1000 trades and that build_ohlcv produces at least 1000 candles, writes the resulting candles as pretty-printed JSON to data/candles with a filename derived from exchange, symbol, timeframe, and start/end timestamps, and prints a summary.
    
    Returns:
        int: Exit code: `0` on success, `1` on error. Error conditions include missing TRADES_FILE, missing or unreadable trades file, malformed JSON, JSON not containing a trades list, fewer than 1000 trades, or fewer than 1000 resulting candles.
    """
    trades_file = senv("TRADES_FILE", "")
    if not trades_file:
        print("ERROR: TRADES_FILE env var is required (path to trades json)")
        return 1

    exchange = senv("EXCHANGE", "kraken").lower()
    symbol = senv("SYMBOL", "BTC/USD")
    timeframe = senv("TIMEFRAME", "5m").lower()
    tf_ms = ienv("TF_MS", 5 * 60 * 1000)

    p = Path(trades_file).expanduser()
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    if not p.exists():
        print(f"ERROR: trades file not found: {p}")
        return 1

    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: failed reading trades json: {e}")
        return 1

    if isinstance(obj, list):
        trades = obj
    elif isinstance(obj, dict):
        for k in ("trades", "data", "result"):
            if k in obj and isinstance(obj[k], list):
                trades = obj[k]
                break
        else:
            print("ERROR: trades json dict has no list under trades/data/result")
            return 1
    else:
        print("ERROR: trades json must be list or dict")
        return 1

    if len(trades) < 1000:
        print(f"ERROR: only {len(trades)} trades found; need more data")
        return 1

    candles = build_ohlcv(trades, tf_ms)
    if len(candles) < 1000:
        print(f"ERROR: only {len(candles)} candles built; need more data")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start_ts = int(candles[0][0])
    end_ts = int(candles[-1][0])
    out = OUT_DIR / f"{exchange}_{symbol_to_fs(symbol)}_{timeframe}_{start_ts}_{end_ts}.json"

    out.write_text(json.dumps(candles, indent=2), encoding="utf-8")
    print(f"WROTE {out}")
    print(f"candles={len(candles)} start={start_ts} end={end_ts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())