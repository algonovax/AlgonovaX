from __future__ import annotations

from typing import Any

def call_strategy_generate_signal(generate_signal, df, **kwargs) -> str:
    """
    Invoke a strategy's flexible `generate_signal` function with a dataframe and normalize its output to a canonical signal string.
    
    This function attempts multiple common call signatures (preferred: generate_signal(df, **kwargs)), then retries using common keyword names for the dataframe (e.g., `df`, `data`, `window`, `candles`, `prices`, `closes`, `close`). For `prices`, `closes`, or `close` it will pass `df["close"]` when the dataframe has a `close` column; otherwise it passes `df`. If a payload attempt raises a `TypeError` the adapter tries the next shape; other exceptions are propagated. If all shaped attempts fail, the function calls `generate_signal(df)` as a last resort. The returned value is coerced to string, stripped, and lowercased.
    
    Parameters:
        generate_signal (callable): Strategy callable that returns a signal-like value and accepts one of several dataframe-oriented signatures.
        df: DataFrame or array-like containing price/candle data (may be a pandas-like object with a `close` column).
        **kwargs: Additional keyword arguments forwarded to the strategy when applicable.
    
    Returns:
        str: One of "buy", "sell", or "hold" (lowercase, stripped).
    """
    # 1) preferred: df first positional
    try:
        out = generate_signal(df, **kwargs)
        return str(out).strip().lower()
    except TypeError:
        pass

    # 2) try keyword shapes
    for payload in (
        {"df": df},
        {"data": df},
        {"window": df},
        {"candles": df},
        {"prices": df["close"] if "close" in getattr(df, "columns", []) else df},
        {"closes": df["close"] if "close" in getattr(df, "columns", []) else df},
        {"close": df["close"] if "close" in getattr(df, "columns", []) else df},
    ):
        try:
            out = generate_signal(**payload, **kwargs)
            return str(out).strip().lower()
        except TypeError:
            continue
        except Exception:
            # real errors should surface in runner; adapter only tries shapes
            raise

    # 3) last resort: raw df only
    out = generate_signal(df)
    return str(out).strip().lower()