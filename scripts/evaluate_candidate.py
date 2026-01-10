#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAND_PATH = ROOT / "data" / "registry" / "candidates.jsonl"
EVAL_PATH = ROOT / "data" / "registry" / "evaluations.jsonl"
BACKTEST = ROOT / "scripts" / "backtest_kraken_5m.py"
REPORT_PATH = ROOT / "data" / "backtest_report.json"

MS_PER_DAY = 24 * 60 * 60 * 1000


def senv(k: str, d: str) -> str:
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else v.strip()


def ienv(k: str, d: int) -> int:
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else int(v)


def fenv(k: str, d: float) -> float:
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else float(v)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def append_jsonl(path: Path, rec: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def candle_ts_range(candle_file: Path) -> tuple[int, int, int]:
    data = json.loads(candle_file.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "candles" in data:
        data = data["candles"]
    if not isinstance(data, list) or not data:
        raise ValueError("bad candle json")
    ts0 = int(data[0][0])
    ts1 = int(data[-1][0])
    return ts0, ts1, len(data)


def run_backtest(env: dict[str, str]) -> dict[str, Any]:
    try:
        if REPORT_PATH.exists():
            REPORT_PATH.unlink()
    except Exception:
        pass

    cmd = [sys.executable, "-u", str(BACKTEST)]
    t0 = time.time()
    proc = subprocess.run(
        cmd,
        env=env,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    elapsed_ms = int((time.time() - t0) * 1000)

    report: dict[str, Any] = {}
    if REPORT_PATH.exists():
        try:
            report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        except Exception:
            report = {}

    return {
        "rc": proc.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout_tail": (proc.stdout or "")[-1200:],
        "stderr_tail": (proc.stderr or "")[-1200:],
        "report": report,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    candle_file_s = senv("CANDLE_FILE", "")
    if not candle_file_s:
        print("ERROR: CANDLE_FILE missing", file=sys.stderr)
        return 2

    candle_file = Path(candle_file_s)
    if not candle_file.exists():
        print(f"ERROR: CANDLE_FILE not found: {candle_file}", file=sys.stderr)
        return 2

    if not CAND_PATH.exists() or CAND_PATH.stat().st_size == 0:
        print("ERROR: No candidates.jsonl found. Run train_candidate.py first.")
        return 0

    fee_rate = fenv("FEE_RATE", 0.001)
    slip_rate = fenv("SLIPPAGE_RATE", 0.0003)
    stake_quote = fenv("STAKE_QUOTE", 100.0)
    min_candles_test = ienv("MIN_CANDLES", 3888)
    test_days = ienv("TEST_DAYS", 15)
    dd_max = fenv("DD_MAX", 0.25)

    _ts0, ts1, _n = candle_ts_range(candle_file)
    end_ms = ts1
    start_ms = end_ms - (test_days * MS_PER_DAY)

    rows = read_jsonl(CAND_PATH)
    train = [
        r
        for r in rows
        if r.get("phase") == "train" and r.get("candle_file") == candle_file_s
    ]
    if not train:
        print(
            "No train candidates found for this candle file. (candidates.jsonl empty or mismatch)"
        )
        return 0

    def train_score(r: dict[str, Any]) -> float:
        rep = r.get("report") or {}
        try:
            return float(rep.get("pnl", -1e18))
        except Exception:
            return -1e18

    train_sorted = sorted(train, key=train_score, reverse=True)[: max(1, int(args.top))]

    print(f"EVAL using candles={Path(candle_file_s).name}")
    print(f"TEST window ms: {start_ms} -> {end_ms} (days={test_days})")
    print(f"TOP={len(train_sorted)} (requested {args.top})")

    EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    ok_count = 0
    for idx, cand in enumerate(train_sorted, start=1):
        params = cand.get("params") or {}
        env = dict(os.environ)

        env["CANDLE_FILE"] = candle_file_s
        env["START_MS"] = str(start_ms)
        env["END_MS"] = str(end_ms)
        env["MIN_CANDLES"] = str(min_candles_test)
        env["FEE_RATE"] = str(fee_rate)
        env["SLIPPAGE_RATE"] = str(slip_rate)
        env["STAKE_QUOTE"] = str(stake_quote)

        for k, v in params.items():
            env[str(k)] = str(v)

        bt = run_backtest(env)
        report = bt.get("report") or {}

        trades = int(report.get("trades") or 0)
        pnl = float(report.get("pnl") or 0.0)

        dd_pct = report.get("max_dd_pct")
        try:
            dd_pct_f = float(dd_pct) if dd_pct is not None else None
        except Exception:
            dd_pct_f = None

        ok = True
        if bt["rc"] != 0:
            ok = False
        if not isinstance(report, dict) or report.get("error"):
            ok = False
        if trades < 1:
            ok = False
        if pnl <= 0.0:
            ok = False
        if dd_pct_f is not None and dd_pct_f > dd_max:
            ok = False

        if ok:
            ok_count += 1

        rec = {
            "ts": int(time.time()),
            "phase": "eval",
            "rank": idx,
            "ok": bool(ok),
            "candle_file": candle_file_s,
            "params": params,
            "trades": trades,
            "pnl": pnl,
            "max_dd": report.get("max_dd"),
            "max_dd_pct": report.get("max_dd_pct"),
            "elapsed_ms": bt.get("elapsed_ms"),
            "report": report,
            "runner_rc": bt.get("rc"),
            "runner_out_tail": bt.get("stdout_tail", ""),
            "runner_err_tail": bt.get("stderr_tail", ""),
            "meta": {
                "fee_rate": fee_rate,
                "slippage_rate": slip_rate,
                "stake_quote": stake_quote,
                "test_days": test_days,
                "dd_max": dd_max,
            },
        }
        append_jsonl(EVAL_PATH, rec)
        print(f"[{idx}/{len(train_sorted)}] ok={ok} trades={trades} pnl={pnl}")

    if ok_count == 0:
        print("No candidates passed eval gates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
