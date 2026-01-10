from __future__ import annotations


def call_strategy_generate_signal(generate_signal, df, **kwargs) -> str:
    """
    Normalizes strategy signatures to a single call site.
    Supports:
      - generate_signal(df)
      - generate_signal(df, **kwargs)
      - generate_signal(closes=<series/list>, **kwargs)
      - generate_signal(window=<df>, **kwargs)
    Returns: "buy" | "sell" | "hold" (lowercase)
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
