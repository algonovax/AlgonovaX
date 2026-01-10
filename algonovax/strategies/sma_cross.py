from __future__ import annotations

import os
import traceback

import pandas as pd

from .indicators import sma
from .types import Signal, Side


def generate_signal(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> Signal:
    try:
        if df is None or df.empty:
            return Signal(Side.HOLD, 0.0, "empty_df")

        if "close" not in df.columns:
            return Signal(Side.HOLD, 0.0, "missing_close")

        close = df["close"]
        if len(close) < max(fast, slow) + 2:
            return Signal(Side.HOLD, 0.0, "insufficient_bars")

        f = sma(close, fast)
        s = sma(close, slow)

        # need last two non-na points
        if (
            pd.isna(f.iloc[-1])
            or pd.isna(s.iloc[-1])
            or pd.isna(f.iloc[-2])
            or pd.isna(s.iloc[-2])
        ):
            return Signal(Side.HOLD, 0.0, "warmup")

        f0, f1 = float(f.iloc[-2]), float(f.iloc[-1])
        s0, s1 = float(s.iloc[-2]), float(s.iloc[-1])

        if f0 <= s0 and f1 > s1:
            return Signal(Side.BUY, 0.65, f"sma_cross_up fast={fast} slow={slow}")
        if f0 >= s0 and f1 < s1:
            return Signal(Side.SELL, 0.65, f"sma_cross_down fast={fast} slow={slow}")

        return Signal(Side.HOLD, 0.0, "no_cross")

    except Exception:
        traceback.print_exc()
        if os.getenv("ALGONOVAX_FAIL_FAST") == "1":
            raise
        return Signal(Side.HOLD, 0.0, "error:Exception")
