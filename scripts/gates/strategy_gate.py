#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


# -----------------------------
# Config / Models
# -----------------------------

@dataclass(frozen=True)
class GateConfig:
    win_rate_min: float = 0.85
    max_dd_max: float = 0.05
    min_trades: int = 1000
    fee_rate: float = 0.001  # 0.10% default; override via CLI
    slippage_rate: float = 0.0005  # 0.05%
    allow_pyramiding: bool = False  # no martingale/DCA


@dataclass
class Trade:
    side: str  # "long" | "short"
    entry_px: float
    exit_px: float
    qty: float
    pnl: float
    is_win: bool


@dataclass
class Result:
    exchange: str
    pair: str
    tf: str
    trades: int
    win_rate: float
    max_dd: float
    net_pnl: float
    passed: bool
    reason: str = ""


# -----------------------------
# Candle loading contract
# -----------------------------
# You must provide candles as an iterable of dicts with at least:
# {"ts": int|float, "open": float, "high": float, "low": float, "close": float, "volume": float}
#
# Implement by either:
# 1) passing --loader "your_module:load_candles"
# OR
# 2) placing CSVs at: data/candles/{exchange}/{pair}/{tf}.csv with columns:
# ts,open,high,low,close,volume
#
# CSV loader is included as fallback.

def load_candles_from_csv(path: Path) -> list[dict[str, float]]:
    import csv

    try:
        rows: list[dict[str, float]] = []
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"ts", "open", "high", "low", "close", "volume"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError(f"CSV missing columns: need {sorted(required)} got {reader.fieldnames}")
            for r in reader:
                rows.append(
                    {
                        "ts": float(r["ts"]),
                        "open": float(r["open"]),
                        "high": float(r["high"]),
                        "low": float(r["low"]),
                        "close": float(r["close"]),
                        "volume": float(r["volume"]),
                    }
                )
        if len(rows) < 10:
            raise ValueError(f"not enough candles: {path}")
        return rows
    except Exception as e:
        raise RuntimeError(f"failed to load candles from {path}: {e}") from e


def resolve_callable(spec: str) -> Callable[..., Any]:
    try:
        mod_name, fn_name = spec.split(":", 1)
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
        if not callable(fn):
            raise TypeError("not callable")
        return fn  # type: ignore[return-value]
    except Exception as e:
        raise RuntimeError(f"bad callable spec {spec!r}: {e}") from e


# -----------------------------
# Strategy contract
# -----------------------------
# Must expose class Strategy with:
# - .name (str)
# - .on_start(cfg: dict, state: Any|None) -> None   (optional)
# - .decide(candle: Any, history: Any) -> Signal
# Signal must have:
# - .side: "hold"|"buy"|"sell"  (or "long"/"short"/"hold" supported below)

def load_strategy(strategy_module: str):
    try:
        mod = importlib.import_module(strategy_module)
        strat_cls = getattr(mod, "Strategy", None)
        if strat_cls is None:
            raise AttributeError("missing Strategy class")
        return strat_cls()
    except Exception as e:
        raise RuntimeError(f"failed to import strategy {strategy_module!r}: {e}") from e


# -----------------------------
# Backtest engine (minimal)
# -----------------------------

def max_drawdown(equity: list[float]) -> float:
    peak = -math.inf
    mdd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > mdd:
                mdd = dd
    return float(mdd)


def simulate(
    candles: list[dict[str, float]],
    strategy: Any,
    gate: GateConfig,
    starting_equity: float = 10_000.0,
    risk_per_trade: float = 0.01,
) -> tuple[list[Trade], list[float]]:
    # Position model: single position at a time. No adds (no DCA/martingale).
    equity = starting_equity
    equity_curve = [equity]
    trades: list[Trade] = []

    pos_side: str | None = None  # "long"|"short"
    entry_px = 0.0
    qty = 0.0

    history: list[dict[str, float]] = []

    def apply_cost(px: float, is_entry: bool) -> float:
        # market impact: worse price by slippage_rate; fees applied to notional
        slip = 1.0 + gate.slippage_rate if is_entry else 1.0 - gate.slippage_rate
        return px * slip

    for i in range(len(candles)):
        c = candles[i]
        history.append(c)
        if len(history) < 50:
            equity_curve.append(equity)
            continue

        try:
            sig = strategy.decide(c, history)
        except Exception as e:
            raise RuntimeError(f"strategy.decide failed at i={i}: {e}") from e

        raw_side = getattr(sig, "side", None) or getattr(sig, "action", None) or "hold"
        side = str(raw_side).lower()

        # normalize
        if side in ("hold", "none", "flat"):
            equity_curve.append(equity)
            continue
        if side in ("buy", "long"):
            want = "long"
        elif side in ("sell", "short"):
            want = "short"
        else:
            equity_curve.append(equity)
            continue

        px = float(c["close"])

        # If no position, open
        if pos_side is None:
            entry_fill = apply_cost(px, is_entry=True)
            risk_amt = equity * risk_per_trade
            # qty sized to risk_amt with simplistic stop distance proxy (1% of price)
            stop_dist = max(entry_fill * 0.01, 1e-9)
            qty = risk_amt / stop_dist
            notional = qty * entry_fill
            fee = notional * gate.fee_rate
            equity -= fee

            pos_side = want
            entry_px = entry_fill
            equity_curve.append(equity)
            continue

        # If same direction and pyramiding disallowed -> ignore
        if pos_side == want and not gate.allow_pyramiding:
            equity_curve.append(equity)
            continue

        # Otherwise, flip/exit current position (close then open new in one bar)
        exit_fill = apply_cost(px, is_entry=False)
        notional_exit = qty * exit_fill
        fee_exit = notional_exit * gate.fee_rate

        if pos_side == "long":
            pnl = (exit_fill - entry_px) * qty - fee_exit
        else:
            pnl = (entry_px - exit_fill) * qty - fee_exit

        equity += pnl
        trades.append(
            Trade(
                side=pos_side,
                entry_px=entry_px,
                exit_px=exit_fill,
                qty=qty,
                pnl=pnl,
                is_win=pnl > 0,
            )
        )

        # open new position in opposite direction
        entry_fill2 = apply_cost(px, is_entry=True)
        notional2 = qty * entry_fill2
        fee2 = notional2 * gate.fee_rate
        equity -= fee2

        pos_side = want
        entry_px = entry_fill2

        equity_curve.append(equity)

        if equity <= 0:
            break

    return trades, equity_curve


# -----------------------------
# Runner / Reporting
# -----------------------------

def eval_one(exchange: str, pair: str, tf: str, candles: list[dict[str, float]], strategy: Any, gate: GateConfig) -> Result:
    try:
        trades, eq = simulate(candles, strategy, gate)
        n = len(trades)
        if n == 0:
            return Result(exchange, pair, tf, 0, 0.0, 0.0, 0.0, False, "no_trades")

        wr = sum(1 for t in trades if t.is_win) / n
        mdd = max_drawdown(eq)
        net = eq[-1] - eq[0]

        if n < gate.min_trades:
            return Result(exchange, pair, tf, n, wr, mdd, net, False, "min_trades_not_met")
        if wr < gate.win_rate_min:
            return Result(exchange, pair, tf, n, wr, mdd, net, False, "win_rate_below_min")
        if mdd > gate.max_dd_max:
            return Result(exchange, pair, tf, n, wr, mdd, net, False, "max_dd_above_max")

        return Result(exchange, pair, tf, n, wr, mdd, net, True, "")
    except Exception as e:
        return Result(exchange, pair, tf, 0, 0.0, 0.0, 0.0, False, f"error:{e}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strategy", required=True, help="python module path, e.g. algonovax.strategies.ema_rsi_atr_engine")
    p.add_argument("--exchanges", required=True, help="comma list, e.g. kraken,coinbase,binanceus")
    p.add_argument("--pairs", required=True, help="comma list, e.g. BTC-USD,ETH-USD (use your canonical format)")
    p.add_argument("--tfs", required=True, help="comma list: 1m,5m,15m,1h")
    p.add_argument("--data-dir", default="data/candles", help="root candle dir for CSV fallback")
    p.add_argument("--loader", default="", help="optional callable spec module:fn to load candles(exchange,pair,tf)->list[dict]")
    p.add_argument("--fee", type=float, default=0.001, help="fee rate, e.g. 0.001 = 0.10%")
    p.add_argument("--slip", type=float, default=0.0005, help="slippage rate, e.g. 0.0005 = 0.05%")
    p.add_argument("--win", type=float, default=0.85)
    p.add_argument("--dd", type=float, default=0.05)
    p.add_argument("--min-trades", type=int, default=1000)
    p.add_argument("--out", default="audit/strategy_gate_report.json")
    p.add_argument("--allow-pyramiding", action="store_true", default=False)
    args = p.parse_args()

    gate = GateConfig(
        win_rate_min=args.win,
        max_dd_max=args.dd,
        min_trades=args.min_trades,
        fee_rate=args.fee,
        slippage_rate=args.slip,
        allow_pyramiding=bool(args.allow_pyramiding),
    )

    strategy = load_strategy(args.strategy)

    loader_fn: Callable[..., Any] | None = None
    if args.loader.strip():
        loader_fn = resolve_callable(args.loader.strip())

    exchanges = [x.strip() for x in args.exchanges.split(",") if x.strip()]
    pairs = [x.strip() for x in args.pairs.split(",") if x.strip()]
    tfs = [x.strip() for x in args.tfs.split(",") if x.strip()]

    results: list[Result] = []
    allowlist: dict[str, dict[str, list[str]]] = {}  # exchange -> pair -> [tfs]

    for ex in exchanges:
        allowlist.setdefault(ex, {})
        for pair in pairs:
            for tf in tfs:
                try:
                    if loader_fn is not None:
                        candles = loader_fn(ex, pair, tf)
                    else:
                        path = Path(args.data_dir) / ex / pair / f"{tf}.csv"
                        candles = load_candles_from_csv(path)
                except Exception as e:
                    results.append(Result(ex, pair, tf, 0, 0.0, 0.0, 0.0, False, f"data_error:{e}"))
                    continue

                r = eval_one(ex, pair, tf, candles, strategy, gate)
                results.append(r)
                if r.passed:
                    allowlist[ex].setdefault(pair, []).append(tf)

    # global pass-rate across matrix
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pass_rate = (passed / total) if total else 0.0

    out = {
        "strategy": args.strategy,
        "gate": dataclasses.asdict(gate),
        "matrix": {"exchanges": exchanges, "pairs": pairs, "tfs": tfs},
        "summary": {"total": total, "passed": passed, "pass_rate": pass_rate},
        "allowlist": allowlist,
        "results": [dataclasses.asdict(r) for r in results],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=False), encoding="utf-8")

    # Exit code: fail if pass_rate < 0.85 OR any critical breach (DD > max or WR < min) on >=15% markets
    if pass_rate < 0.85:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as e:
        sys.stderr.write(f"FATAL: {e}\n")
        raise SystemExit(1)
