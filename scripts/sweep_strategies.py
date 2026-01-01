#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "backtest_multi_5m.py"
REPORT = ROOT / "data" / "backtest_report.json"
OUT_SEEDS = ROOT / "data" / "registry" / "seeds.jsonl"

def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")

def _run(env: dict[str, str]) -> dict[str, Any]:
    try:
        if REPORT.exists():
            REPORT.unlink()
    except Exception:
        pass

    t0 = time.time()
    cp = subprocess.run(
        [sys.executable, "-u", str(RUNNER)],
        env=env,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    elapsed_ms = int((time.time() - t0) * 1000)

    rep: dict[str, Any] = {}
    if REPORT.exists():
        try:
            rep = json.loads(REPORT.read_text(encoding="utf-8"))
        except Exception:
            rep = {}

    return {
        "rc": cp.returncode,
        "elapsed_ms": elapsed_ms,
        "report": rep,
        "out_tail": (cp.stdout or "")[-1200:],
        "err_tail": (cp.stderr or "")[-1200:],
    }

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=int(os.environ.get("SWEEP_ITERS", "80")))
    ap.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "1337")))
    ap.add_argument("--keep", type=int, default=int(os.environ.get("SWEEP_KEEP", "12")))
    ap.add_argument("--candle-file", type=str, default=os.environ.get("CANDLE_FILE", ""))
    args = ap.parse_args()

    if not args.candle_file:
        print("ERROR: set CANDLE_FILE or pass --candle-file", file=sys.stderr)
        return 2

    candle_path = Path(args.candle_file)
    if not candle_path.exists():
        print(f"ERROR: candle file missing: {candle_path}", file=sys.stderr)
        return 2

    random.seed(args.seed)

    # fixed costs for sweep (override via env if you want)
    base_env = dict(os.environ)
    base_env["CANDLE_FILE"] = str(candle_path)
    base_env.setdefault("FEE_RATE", "0.001")
    base_env.setdefault("SLIPPAGE_RATE", "0.0003")
    base_env.setdefault("STAKE_QUOTE", "100")
    base_env.setdefault("MIN_CANDLES", "3888")

    # keep this on by default; you can export MIN_ATR_PCT=0 to disable
    base_env.setdefault("MIN_ATR_PCT", "0.0006")
    base_env.setdefault("BREAKOUT_ATR_BUFFER", "0.25")

    strategies = ["donchian_breakout_atr", "ema_pullback", "rsi_mean_revert"]

    trials: list[tuple[float, dict[str, Any]]] = []

    for i in range(1, args.iters + 1):
        strat = random.choice(strategies)

        env = dict(base_env)
        env["STRATEGY"] = strat

        # shared knobs
        env["ATR_N"] = str(random.randint(10, 30))
        env["STOP_K"] = str(round(random.uniform(1.0, 4.0), 2))
        env["TAKE_K"] = str(round(random.uniform(1.0, 6.0), 2))
        env["MAX_HOLD_BARS"] = str(random.choice([24, 48, 72, 96, 144]))

        # strategy-specific knobs
        if strat == "donchian_breakout_atr":
            env["DONCHIAN_N"] = str(random.randint(10, 60))
        elif strat == "ema_pullback":
            env["TREND_EMA"] = str(random.choice([50, 80, 120, 160]))
            env["SLOPE_BARS"] = str(random.choice([2, 3, 5, 8]))
            env["PULLBACK_MAX"] = str(random.choice([0.0015, 0.0025, 0.0040]))  # 0.15%, 0.25%, 0.40%
        elif strat == "rsi_mean_revert":
            env["RSI_N"] = str(random.choice([10, 14, 21]))
            env["RSI_BUY"] = str(random.choice([22.0, 25.0, 28.0, 30.0]))
            env["RSI_SELL"] = str(random.choice([50.0, 55.0, 60.0]))

        bt = _run(env)
        rep = bt.get("report") or {}

        if bt["rc"] != 0 or not isinstance(rep, dict) or rep.get("error"):
            score = -1e18
        else:
            pnl = float(rep.get("pnl", 0.0))
            dd = float(rep.get("max_dd_pct", 1.0))
            trades = int(rep.get("trades", 0))
            pnl_per_trade = (pnl / trades) if trades else 0.0
            # simple robust score (you can tune later)
            score = pnl - (dd * 50.0) + (pnl_per_trade * 10.0)

        rec = {
            "ts": int(time.time()),
            "phase": "seed",
            "iter": i,
            "candle_file": str(candle_path),
            "strategy": strat,
            "env_params": {k: env[k] for k in env.keys() if k in {
                "STRATEGY","DONCHIAN_N","ATR_N","STOP_K","TAKE_K","MAX_HOLD_BARS",
                "MIN_ATR_PCT","BREAKOUT_ATR_BUFFER","TREND_EMA","SLOPE_BARS","PULLBACK_MAX",
                "RSI_N","RSI_BUY","RSI_SELL",
            }},
            "report": rep,
            "score": float(score),
            "meta": {
                "fee_rate": float(base_env.get("FEE_RATE","0.001")),
                "slippage_rate": float(base_env.get("SLIPPAGE_RATE","0.0003")),
                "stake_quote": float(base_env.get("STAKE_QUOTE","100")),
            },
        }
        trials.append((float(score), rec))
        print(f"[{i}/{args.iters}] strat={strat} score={score:.6f} pnl={float(rep.get('pnl',0.0)):.6f} dd={float(rep.get('max_dd_pct',0.0)):.6f} trades={int(rep.get('trades',0))}")

    trials.sort(key=lambda x: x[0], reverse=True)
    keep = max(1, min(args.keep, len(trials)))

    # overwrite seeds each run
    OUT_SEEDS.parent.mkdir(parents=True, exist_ok=True)
    OUT_SEEDS.write_text("", encoding="utf-8")

    for _, rec in trials[:keep]:
        _append_jsonl(OUT_SEEDS, rec)

    print(f"WROTE {keep} seeds -> {OUT_SEEDS}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
