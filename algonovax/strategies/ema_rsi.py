from __future__ import annotations

import os
import traceback

import pandas as pd

from .types import Signal, Side


def generate_signal(
    df: pd.DataFrame,
    ema_short: int = 5,
    ema_long: int = 20,
    rsi_n: int = 14,
    rsi_overbought: float = 70.0,
    rsi_oversold: float = 30.0,
) -> Signal:
    try:
        if df is None or df.empty:
            return Signal(Side.HOLD, 0.0, "empty_df")

        req = ["close"]
        missing = [c for c in req if c not in df.columns]
        if missing:
            return Signal(Side.HOLD, 0.0, f"missing_cols:{','.join(missing)}")

        close = df["close"].astype(float)

        ema_s = close.ewm(span=ema_short, adjust=False).mean()
        ema_l = close.ewm(span=ema_long, adjust=False).mean()

        delta = close.diff()
        gain = delta.clip(lower=0.0)
        loss = (-delta).clip(lower=0.0)

        avg_gain = gain.rolling(rsi_n).mean()
        avg_loss = loss.rolling(rsi_n).mean()

        rs = avg_gain / avg_loss.replace(0.0, pd.NA)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        if pd.isna(ema_s.iloc[-1]) or pd.isna(ema_l.iloc[-1]) or pd.isna(rsi.iloc[-1]):
            return Signal(Side.HOLD, 0.0, "warmup")

        es = float(ema_s.iloc[-1])
        el = float(ema_l.iloc[-1])
        r = float(rsi.iloc[-1])

        if es > el and r < rsi_overbought:
            return Signal(
                Side.BUY,
                0.55,
                f"ema_rsi_buy es>={ema_short} el>={ema_long} rsi={r:.1f}",
            )
        if es < el and r > rsi_oversold:
            return Signal(
                Side.SELL,
                0.55,
                f"ema_rsi_sell es<={ema_short} el<={ema_long} rsi={r:.1f}",
            )

        return Signal(Side.HOLD, 0.0, "no_setup")

    except Exception:
        traceback.print_exc()
        if os.getenv("ALGONOVAX_FAIL_FAST") == "1":
            raise
        return Signal(Side.HOLD, 0.0, "error:Exception")
