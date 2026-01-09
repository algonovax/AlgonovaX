from __future__ import annotations

import importlib
import pkgutil

import numpy as np
import pandas as pd

import algonovax.strategies as strategies


def make_df(n: int = 600) -> pd.DataFrame:
    close = np.array([100 + (i % 7) for i in range(n)], dtype=float)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    volume = np.full(n, 1000.0)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def main() -> int:
    df = make_df()

    failures: list[str] = []
    for m in pkgutil.iter_modules(strategies.__path__):
        if m.name in {"types", "__init__", "registry", "indicators", "_adapter"}:
            continue

        modname = f"{strategies.__name__}.{m.name}"
        mod = importlib.import_module(modname)
        fn = getattr(mod, "generate_signal", None)
        if not callable(fn):
            continue

        try:
            sig = fn(df)
            side = getattr(sig, "side", None)
            reason = getattr(sig, "reason", None)
            print(modname, "->", side, reason)

            if isinstance(reason, str) and reason.startswith("error:"):
                failures.append(f"{modname}: {reason}")

        except Exception as e:
            failures.append(f"{modname}: {type(e).__name__}: {e}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" -", f)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
