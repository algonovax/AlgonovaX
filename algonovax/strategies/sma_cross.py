from __future__ import annotations

import os
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd

from .indicators import sma
from .types import Signal, Side




def generate_signal(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> Signal:
    """
    Generate a trading Signal based on a fast/slow SMA crossover using the DataFrame's `close` series.
    
    Parameters:
        df (pd.DataFrame): Price data containing a `close` column.
        fast (int): Window length for the fast SMA.
        slow (int): Window length for the slow SMA.
    
    Returns:
        Signal: A Signal with Side in {BUY, SELL, HOLD}, a confidence score, and a reason string.
            Known reason values include:
                - "empty_df" (input is None or empty)
                - "missing_close" (no `close` column)
                - "insufficient_bars" (fewer than max(fast, slow) + 2 bars)
                - "warmup" (recent SMA values are NaN)
                - "sma_cross_up fast={fast} slow={slow}" (fast crossed above slow; BUY, confidence 0.65)
                - "sma_cross_down fast={fast} slow={slow}" (fast crossed below slow; SELL, confidence 0.65)
                - "no_cross" (no crossover detected; HOLD)
                - "error:Exception" (an error occurred; HOLD)
    
    Raises:
        Exception: Re-raises any unexpected exception if the environment variable ALGONOVAX_FAIL_FAST is "1".
    """
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
        if pd.isna(f.iloc[-1]) or pd.isna(s.iloc[-1]) or pd.isna(f.iloc[-2]) or pd.isna(s.iloc[-2]):
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