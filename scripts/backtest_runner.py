#!/usr/bin/env python3
from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Any

import pandas as pd

from algonovax.utils.jsonutil import dump as json_dump
from algonovax.strategies.sma_cross import generate_signal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "backtest_last.json"


def main() -> int:
    """
    Run a simple synthetic backtest, compute a trading signal, and persist the result.
    
    Builds a 60-point synthetic close price series, constructs a DataFrame, calls the SMA cross strategy to produce a signal, and writes a JSON payload describing the run to the module-level OUT path. The function prints the output path and contents. On exception it prints a traceback, attempts to write an error payload to OUT, and may re-raise the original exception if the environment variable ALGONOVAX_FAIL_FAST is set to "1".
    
    Returns:
        int: `0` on success, `1` on failure.
    """
    try:
        closes = [100 + (i % 7) for i in range(60)]
        df = pd.DataFrame({"close": closes})

        signal = generate_signal(df)

        payload: dict[str, Any] = {
            "strategy": "sma_cross",
            "signal": signal,
            "n_closes": len(closes),
        }

        json_dump(payload, OUT)
        print(f"WROTE {OUT}")
        print(OUT.read_text(encoding="utf-8"))
        return 0

    except Exception:
        traceback.print_exc()
        if os.getenv("ALGONOVAX_FAIL_FAST") == "1":
            raise
        try:
            json_dump({"error": "backtest_runner_failed"}, OUT)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())