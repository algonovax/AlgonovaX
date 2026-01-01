#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
import re
from typing import Any, Dict, Tuple


ROOT = Path(__file__).resolve().parents[1]
REG_DIR = ROOT / "data" / "registry"
REG_DIR.mkdir(parents=True, exist_ok=True)

RUNNER = ROOT / "scripts" / "backtest_kraken_5m.py"
OUT_REPORT = ROOT / "data" / "backtest_report.json"

# Expected candle filename:
# kraken_BTC_USD_5m_<start_ms>_<end_ms>.json
def parse_candle_filename(name: str):
    stem = Path(name).name
    m = re.match(r"^kraken_[A-Z0-9]+_[A-Z0-9]+_5m_(\d+)_(\d+)\.json$", stem)
    if not m:
        raise ValueError(f"Unexpected candle filename: {stem}")
    return int(m.group(1)), int(m.group(2))


def _append_jsonl(path: Path, obj: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, sort_keys=True) + "\n")
    except Exception as e:
        print(f"ERROR: failed writing registry: {e}")

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=int(os.environ.get("TRAIN_ITERS", "60")))
    ap.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "1337")))
    ap.add_argument("--candle-file", type=str, default=os.environ.get("CANDLE_FILE", ""))
    ap.add_argument("--keep-top", type=int, default=int(os.environ.get("TRAIN_KEEP_TOP", "60")))

    args = ap.parse_args()

    if not args.candle_file:
        print("ERROR: candle file not provided (use --candle-file or set CANDLE_FILE)")
        return 2

    candle_path = Path(args.candle_file)
    if not candle_path.exists():
        print(f"ERROR: candle file missing: {candle_path}")
        return 2

    # sanity + window derivation
    try:
        file_start_ms, file_end_ms = parse_candle_filename(candle_path.name)
    except Exception as e:
        print(f"ERROR: {e}")
        return 2
    train_days = int(os.environ.get("TRAIN_DAYS","30"))
    test_days  = int(os.environ.get("TEST_DAYS","15"))
    ms_day = 24*60*60*1000
    test_end_ms = file_end_ms
    test_start_ms = test_end_ms - test_days*ms_day
    train_end_ms = test_start_ms
    train_start_ms = train_end_ms - train_days*ms_day

    reg_path = REG_DIR / "candidates.jsonl"
    random.seed(args.seed)

    print(f"USING candles={candle_path.name}")
    print(f"ITERATIONS={args.iterations} SEED={args.seed}")

    ok_any = False
    train_rows = []  # collect (pnl, rec)

    for i in range(1, args.iterations + 1):
        params = {
    "DONCHIAN_N": random.randint(10, 60),
    "ATR_N": random.randint(10, 30),
    "STOP_K": round(random.uniform(1.0, 4.0), 2),
    "TAKE_K": round(random.uniform(1.0, 6.0), 2),
    "MAX_HOLD_BARS": random.choice([24, 48, 72, 96, 144]),
}
        t0 = time.time()
        rec = {
            "ts": int(time.time()),
            "phase": "train",
            "ok": False,
            "iter": i,
            "seed": args.seed,
            "candle_file": str(candle_path),
            "params": params,
        }
        try:
            # Run backtest runner if it exists (your real implementation may already do this elsewhere)
            if RUNNER.exists():
                env = os.environ.copy()
                env["CANDLE_FILE"] = str(candle_path)
                env["START_MS"] = str(train_start_ms)
                env["END_MS"] = str(train_end_ms)
                for k, v in params.items():
                    env[str(k)] = str(v)
                cp = subprocess.run(
                    [sys.executable, "-u", str(RUNNER)],
                    env=env,
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                rec["runner_rc"] = cp.returncode
                rec["runner_out_tail"] = (cp.stdout or "")[-2000:]
                rec["runner_err_tail"] = (cp.stderr or "")[-2000:]
                if cp.returncode != 0:
                    raise RuntimeError(f"runner rc={cp.returncode}")
            else:
                raise RuntimeError(f"missing runner: {RUNNER}")

            # Candidate considered "ok" if report exists and indicates trades > 0 (weak, but non-zero)
            if OUT_REPORT.exists():
                try:
                    r = json.loads(OUT_REPORT.read_text(encoding="utf-8"))
                    rec["report"] = r
                    trades = int(r.get("trades", 0)) if isinstance(r, dict) else 0
                    rec["ok"] = (trades > 0 and float(r.get("pnl", 0.0)) > 0.0)
                except Exception as e:
                    rec["error"] = f"bad report json: {e}"
            else:
                rec["error"] = "missing backtest_report.json"

            pnl = 0.0
            try:
                pnl = float(rec.get("report", {}).get("pnl", 0.0))
            except Exception:
                pnl = 0.0
            train_rows.append((pnl, rec))
            if rec["ok"]:
                ok_any = True
                print(f"[{i}/{args.iterations}] OK")
            else:
                print(f"[{i}/{args.iterations}] FAIL")

        except Exception as e:
            rec["error"] = str(e)
            print(f"[{i}/{args.iterations}] FAIL")
        finally:
            rec["elapsed_ms"] = int((time.time() - t0) * 1000)
            pass

    # write top candidates for eval
    train_rows.sort(key=lambda x: x[0], reverse=True)
    keep = max(1, min(int(args.keep_top), len(train_rows)))
    for pnl, rec in train_rows[:keep]:
        _append_jsonl(reg_path, rec)
    print(f"WROTE {keep} candidates -> {reg_path}")
    if not ok_any:
        print("No profitable candidates on TRAIN window.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
