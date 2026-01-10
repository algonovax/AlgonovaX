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
