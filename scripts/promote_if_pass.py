#!/usr/bin/env python3
import os
import json
from pathlib import Path

EVAL_PATH = Path("data/registry/evaluations.jsonl")
OUT_PATH = Path("data/registry/passing.jsonl")


def _f(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return float(default)


def main() -> int:
    if not EVAL_PATH.exists():
        print("No evaluations found. Run evaluate_candidate.py first.")
        return 0

    rows = []
    for line in EVAL_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("phase") != "eval":
            continue
        rows.append(rec)

    if not rows:
        print("No passing evaluations found. (evaluations.jsonl empty)")
        return 0

    # Promote gates
    min_trades = int(os.environ.get("PROMOTE_MIN_TRADES", "1"))
    min_pnl = float(os.environ.get("PROMOTE_MIN_PNL", "0.0"))
    max_dd_pct = float(
        os.environ.get("PROMOTE_MAX_DD_PCT", "1.0")
    )  # only used if dd key exists

    ok_rows = []
    for r in rows:
        ok = bool(r.get("ok"))
        trades = int(r.get("trades") or (r.get("report") or {}).get("trades") or 0)
        pnl = _f(
            r.get("pnl") if "pnl" in r else (r.get("report") or {}).get("pnl"), -1e18
        )

        rep = r.get("report") or {}
        dd_pct = rep.get("max_dd_pct", rep.get("dd_pct", None))  # support either name

        reasons = []
        if not ok:
            reasons.append("ok=false")
        if trades < min_trades:
            reasons.append(f"trades<{min_trades}")
        if pnl <= min_pnl:
            reasons.append(f"pnl<={min_pnl}")

        # Only enforce DD gate if the metric exists
        if dd_pct is not None:
            dd_pct_f = _f(dd_pct, 0.0)
            if dd_pct_f > max_dd_pct:
                reasons.append(f"dd_pct>{max_dd_pct}")

        if reasons:
            continue
        ok_rows.append(r)

    if not ok_rows:
        # Debug: show best 5 by pnl with why they failed
        rows_sorted = sorted(
            rows,
            key=lambda r: _f(
                r.get("pnl") if "pnl" in r else (r.get("report") or {}).get("pnl"),
                -1e18,
            ),
            reverse=True,
        )
        print("No candidates passed gates.")
        print(
            f"GATES: ok=true, trades>={min_trades}, pnl>{min_pnl}, dd_pct<={max_dd_pct} (only if dd metric present)"
        )
        print("Top 5 by pnl:")
        for r in rows_sorted[:5]:
            rep = r.get("report") or {}
            trades = int(r.get("trades") or rep.get("trades") or 0)
            pnl = _f(r.get("pnl") if "pnl" in r else rep.get("pnl"), -1e18)
            dd_pct = rep.get("max_dd_pct", rep.get("dd_pct", None))
            print(
                f"- pnl={pnl:.6f} trades={trades} ok={bool(r.get('ok'))} dd_pct={dd_pct} params={r.get('params')}"
            )
        return 0

    best = sorted(
        ok_rows,
        key=lambda r: _f(
            r.get("pnl") if "pnl" in r else (r.get("report") or {}).get("pnl"), -1e18
        ),
        reverse=True,
    )[0]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(best, ensure_ascii=False) + "\n")

    pnl = _f(
        best.get("pnl") if "pnl" in best else (best.get("report") or {}).get("pnl"), 0.0
    )
    trades = int(best.get("trades") or (best.get("report") or {}).get("trades") or 0)
    print(f"PROMOTED: pnl={pnl:.6f} trades={trades} params={best.get('params')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
