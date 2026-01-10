#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUT_REPORT = ROOT / "data" / "backtest_report.json"
OUT_TRADES = ROOT / "data" / "backtest_trades.json"


def load_candles(path: Path) -> List[List[float]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "candles" in data:
        data = data["candles"]
    if not isinstance(data, list) or not data:
        raise ValueError("bad candle json")
    return data


def senv(k: str, d: str) -> str:
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else v.strip()


def ienv(k: str, d: int) -> int:
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else int(v)


def fenv(k: str, d: float) -> float:
    v = os.environ.get(k)
    return d if v is None or v.strip() == "" else float(v)


def clamp_window(
    candles: List[List[float]], start_ms: int, end_ms: int
) -> List[List[float]]:
    if start_ms <= 0 and end_ms <= 0:
        return candles
    out: List[List[float]] = []
    for r in candles:
        ts = int(r[0])
        if start_ms and ts < start_ms:
            continue
        if end_ms and ts > end_ms:
            continue
        out.append(r)
    return out


def rolling_max(vals: List[float], n: int, idx: int) -> float:
    a = max(0, idx - n)
    return max(vals[a:idx]) if idx > a else vals[idx]


def ema(series: List[float], n: int) -> List[float]:
    if n <= 1:
        return [float(x) for x in series]
    alpha = 2.0 / (n + 1.0)
    out: List[float] = [float(series[0])]
    for i in range(1, len(series)):
        out.append(alpha * float(series[i]) + (1.0 - alpha) * out[-1])
    return out


def rsi(close: List[float], n: int) -> List[float]:
    if n <= 1:
        return [50.0] * len(close)
    gains = [0.0] * len(close)
    losses = [0.0] * len(close)
    for i in range(1, len(close)):
        d = float(close[i]) - float(close[i - 1])
        gains[i] = max(0.0, d)
        losses[i] = max(0.0, -d)
    out = [50.0] * len(close)

    w0 = min(n, len(close) - 1)
    if w0 <= 0:
        return out
    avg_g = sum(gains[1 : w0 + 1]) / w0
    avg_l = sum(losses[1 : w0 + 1]) / w0

    for i in range(w0 + 1, len(close)):
        avg_g = (avg_g * (n - 1) + gains[i]) / n
        avg_l = (avg_l * (n - 1) + losses[i]) / n
        rs = (avg_g / avg_l) if avg_l > 0 else 999.0
        out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def compute_atr(
    high: List[float], low: List[float], close: List[float], n: int
) -> List[float]:
    tr: List[float] = []
    for i in range(len(close)):
        if i == 0:
            tr.append(float(high[i]) - float(low[i]))
        else:
            tr.append(
                max(
                    float(high[i]) - float(low[i]),
                    abs(float(high[i]) - float(close[i - 1])),
                    abs(float(low[i]) - float(close[i - 1])),
                )
            )
    out: List[float] = [0.0] * len(close)
    n = max(1, int(n))
    for i in range(len(close)):
        a = max(0, i - n + 1)
        w = tr[a : i + 1]
        out[i] = (sum(w) / len(w)) if w else 0.0
    return out


def max_drawdown(equity: List[float]) -> Tuple[float, float]:
    if not equity:
        return 0.0, 0.0
    peak = float(equity[0])
    max_dd = 0.0
    for x in equity:
        x = float(x)
        if x > peak:
            peak = x
        dd = peak - x
        if dd > max_dd:
            max_dd = dd
    max_dd_pct = (max_dd / peak) if peak > 0 else 0.0
    return float(max_dd), float(max_dd_pct)


@dataclass
class Trade:
    strategy: str
    entry_ts: int
    entry_px: float
    exit_ts: int
    exit_px: float
    qty: float
    pnl: float
    reason: str


def entry_signal(
    strategy: str, i: int, high: List[float], close: List[float], atr: List[float]
) -> bool:
    if strategy == "donchian_breakout_atr":
        donchian_n = ienv("DONCHIAN_N", 20)
        min_atr_pct = fenv("MIN_ATR_PCT", 0.0)
        buf_atr = fenv("BREAKOUT_ATR_BUFFER", 0.0)
        dh = rolling_max(high, donchian_n, i)
        if float(close[i]) <= 0:
            return False
        if min_atr_pct > 0 and (float(atr[i]) / float(close[i])) < min_atr_pct:
            return False
        return float(close[i]) > (float(dh) + float(buf_atr) * float(atr[i]))

    if strategy == "ema_pullback":
        trend_ema = ienv("TREND_EMA", 80)
        pullback_max = fenv("PULLBACK_MAX", 0.0025)
        slope_bars = ienv("SLOPE_BARS", 3)
        min_atr_pct = fenv("MIN_ATR_PCT", 0.0)
        ema_line = ema(close, trend_ema)
        if i <= max(trend_ema, slope_bars) + 2:
            return False
        if float(close[i]) <= 0:
            return False
        if min_atr_pct > 0 and (float(atr[i]) / float(close[i])) < min_atr_pct:
            return False
        slope = float(ema_line[i] - ema_line[i - slope_bars])
        if slope <= 0:
            return False
        dist = (
            (float(close[i]) - float(ema_line[i])) / float(ema_line[i])
            if float(ema_line[i])
            else 0.0
        )
        return float(close[i]) > float(ema_line[i]) and dist <= pullback_max

    if strategy == "rsi_mean_revert":
        rsi_n = ienv("RSI_N", 14)
        rsi_buy = fenv("RSI_BUY", 28.0)
        min_atr_pct = fenv("MIN_ATR_PCT", 0.0)
        r = rsi(close, rsi_n)
        if i <= rsi_n + 2:
            return False
        if float(close[i]) <= 0:
            return False
        if min_atr_pct > 0 and (float(atr[i]) / float(close[i])) < min_atr_pct:
            return False
        return float(r[i]) <= rsi_buy

    raise ValueError(f"unknown STRATEGY={strategy}")


def exit_signal(
    strategy: str,
    i: int,
    high: List[float],
    low: List[float],
    close: List[float],
    atr: List[float],
    entry_i: int,
    stop_px: float,
    take_px: float,
) -> Tuple[bool, float, str]:
    slip_rate = fenv("SLIPPAGE_RATE", 0.0003)

    hit_stop = float(low[i]) <= float(stop_px)
    hit_take = float(high[i]) >= float(take_px)

    if hit_stop:
        return True, float(stop_px) * (1.0 - slip_rate), "stop"
    if hit_take:
        return True, float(take_px) * (1.0 - slip_rate), "take"

    max_hold = ienv("MAX_HOLD_BARS", 96)
    if (i - entry_i) >= max_hold:
        return True, float(close[i]) * (1.0 - slip_rate), "time"

    if strategy == "rsi_mean_revert":
        rsi_n = ienv("RSI_N", 14)
        rsi_sell = fenv("RSI_SELL", 55.0)
        r = rsi(close, rsi_n)
        if float(r[i]) >= rsi_sell:
            return True, float(close[i]) * (1.0 - slip_rate), "rsi_exit"

    return False, 0.0, ""


def main() -> int:
    try:
        candle_file = senv("CANDLE_FILE", "")
        if not candle_file:
            raise ValueError("CANDLE_FILE env missing")

        strategy = senv("STRATEGY", "donchian_breakout_atr")

        candles = load_candles(Path(candle_file))
        start_ms = int(senv("START_MS", "0"))
        end_ms = int(senv("END_MS", "0"))
        candles = clamp_window(candles, start_ms, end_ms)

        min_candles = ienv("MIN_CANDLES", 1)
        if len(candles) < min_candles:
            raise ValueError(f"not enough candles: {len(candles)} < {min_candles}")

        fee_rate = fenv("FEE_RATE", 0.001)
        slip_rate = fenv("SLIPPAGE_RATE", 0.0003)
        stake_quote = fenv("STAKE_QUOTE", 100.0)

        atr_n = ienv("ATR_N", 14)
        stop_k = fenv("STOP_K", 2.0)
        take_k = fenv("TAKE_K", 3.0)

        ts = [int(r[0]) for r in candles]
        high = [float(r[2]) for r in candles]
        low = [float(r[3]) for r in candles]
        close = [float(r[4]) for r in candles]

        atr = compute_atr(high, low, close, atr_n)

        trades: List[Trade] = []
        cum_pnl = 0.0
        equity: List[float] = [float(stake_quote)]

        in_pos = False
        entry_i = -1
        entry_px = 0.0
        qty = 0.0
        stop_px = 0.0
        take_px = 0.0

        warmup = (
            max(ienv("DONCHIAN_N", 20), atr_n, ienv("TREND_EMA", 80), ienv("RSI_N", 14))
            + 2
        )

        for i in range(warmup, len(candles)):
            if not in_pos:
                if entry_signal(strategy, i, high, close, atr):
                    px = float(close[i]) * (1.0 + slip_rate)
                    qty = (stake_quote / px) * (1.0 - fee_rate)
                    entry_px = px
                    entry_i = i

                    a = float(atr[i])
                    stop_px = entry_px - stop_k * a
                    take_px = entry_px + take_k * a
                    in_pos = True
            else:
                do_exit, exit_px, reason = exit_signal(
                    strategy, i, high, low, close, atr, entry_i, stop_px, take_px
                )
                if do_exit:
                    proceeds = qty * float(exit_px) * (1.0 - fee_rate)
                    pnl = float(proceeds) - float(stake_quote)
                    cum_pnl += pnl
                    equity.append(float(stake_quote) + float(cum_pnl))

                    trades.append(
                        Trade(
                            strategy=strategy,
                            entry_ts=ts[entry_i],
                            entry_px=float(entry_px),
                            exit_ts=ts[i],
                            exit_px=float(exit_px),
                            qty=float(qty),
                            pnl=float(pnl),
                            reason=str(reason),
                        )
                    )
                    in_pos = False
                    entry_i = -1

        pnl = sum(t.pnl for t in trades)
        wins = sum(1 for t in trades if t.pnl > 0)
        losses = sum(1 for t in trades if t.pnl <= 0)
        trades_n = len(trades)
        max_dd, max_dd_pct = max_drawdown(equity)
        pnl_pct = (pnl / stake_quote) * 100.0 if stake_quote else 0.0

        OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        OUT_TRADES.parent.mkdir(parents=True, exist_ok=True)

        report: dict[str, Any] = {
            "strategy": strategy,
            "candle_file": candle_file,
            "candles": len(candles),
            "trades": trades_n,
            "wins": wins,
            "losses": losses,
            "pnl": float(pnl),
            "max_dd": float(max_dd),
            "max_dd_pct": float(max_dd_pct),
            "pnl_pct": float(pnl_pct),
            "params": {
                k: os.environ.get(k)
                for k in [
                    "STRATEGY",
                    "DONCHIAN_N",
                    "ATR_N",
                    "STOP_K",
                    "TAKE_K",
                    "MAX_HOLD_BARS",
                    "MIN_ATR_PCT",
                    "BREAKOUT_ATR_BUFFER",
                    "TREND_EMA",
                    "SLOPE_BARS",
                    "PULLBACK_MAX",
                    "RSI_N",
                    "RSI_BUY",
                    "RSI_SELL",
                ]
                if os.environ.get(k) is not None
            },
            "costs": {
                "fee_rate": float(fee_rate),
                "slippage_rate": float(slip_rate),
                "stake_quote": float(stake_quote),
            },
        }

        OUT_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        OUT_TRADES.write_text(
            json.dumps([t.__dict__ for t in trades], indent=2), encoding="utf-8"
        )
        return 0

    except Exception as e:
        try:
            OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
            OUT_REPORT.write_text(
                json.dumps({"error": str(e)}, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
