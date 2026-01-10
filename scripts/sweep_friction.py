#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BT = ROOT / "scripts" / "backtest_kraken_5m.py"
REPORT = ROOT / "data" / "backtest_report.json"


def main() -> int:
    candle = os.environ.get("CANDLE_FILE", "").strip()
    if not candle:
        print("ERROR: CANDLE_FILE not set/exported", file=sys.stderr)
        return 2

    base_env = dict(os.environ)
    base_env["CANDLE_FILE"] = candle
    base_env.setdefault("TEST_DAYS", "15")

    fees = [0.0, 0.0005, 0.001, 0.0015, 0.002]
    slips = [0.0, 0.0001, 0.0002, 0.0003, 0.0005]

    print("fee,slip,trades,pnl,pnl_per_trade,max_dd_pct")

    for fee in fees:
        for slip in slips:
            env = dict(base_env)
            env["FEE_RATE"] = str(fee)
            env["SLIPPAGE_RATE"] = str(slip)

            try:
                if REPORT.exists():
                    REPORT.unlink()
            except Exception:
                pass

            proc = subprocess.run(
                [sys.executable, "-u", str(BT)],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if not REPORT.exists():
                continue

            try:
                report = json.loads(REPORT.read_text())
            except Exception:
                continue

            trades = int(report.get("trades", 0))
            pnl = float(report.get("pnl", 0.0))
            dd = float(report.get("max_dd_pct", 0.0))
            pnl_per_trade = (pnl / trades) if trades else 0.0

            print(
                f"{fee:.4f},{slip:.4f},{trades},{pnl:.6f},{pnl_per_trade:.6f},{dd:.6f}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
