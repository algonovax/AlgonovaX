from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Signal:
    # action: "hold" | "enter" | "exit"
    action: str
    reason: str = ""
    stake_quote: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _get(c: Any, k: str, default: float = 0.0) -> float:
    if isinstance(c, dict):
        return _f(c.get(k), default)
    return _f(getattr(c, k, default), default)


def _ema(vals: list[float], period: int) -> float | None:
    if period <= 1:
        return vals[-1] if vals else None
    if len(vals) < period:
        return None
    a = 2.0 / (period + 1.0)
    e = vals[0]
    for v in vals[1:]:
        e = a * v + (1.0 - a) * e
    return e


def _rsi(closes: list[float], period: int) -> float | None:
    if period <= 1 or len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gains += d
        else:
            losses += -d
    if losses == 0.0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> float | None:
    if period <= 1 or len(closes) < period + 1:
        return None
    trs: list[float] = []
    for i in range(-period, 0):
        h = highs[i]
        lo = lows[i]
        pc = closes[i - 1]
        tr = max(h - lo, abs(h - pc), abs(lo - pc))
        trs.append(tr)
    return (sum(trs) / float(period)) if trs else None


class Strategy:
    # defaults so decide() works even if on_start() isn't called by runner
    warmup = 64
    ema_fast = 12
    ema_slow = 26
    rsi_period = 14
    atr_period = 14
    sl_atr_mult = 1.5
    tp_atr_mult = 2.5
    fallback_sl_pct = 0.01
    fallback_tp_pct = 0.02
    rsi_enter_max = 70.0
    rsi_exit_min = 35.0

    # defensive fallback (in case adapter changes)
    def need(self, name: str, value: float | int | None) -> float:
        if value is None:
            raise ValueError(f"missing required indicator: {name}")
        return float(value)

    # --- compatibility shim (engine expects on_candle) ---
    def on_candle(self, candle, state=None):
        # Engine calls: on_candle(candle_dict, state_dict)
        # Strategy historically uses decide(candle, history/state)
        try:
            return self.decide(candle, state)
        except TypeError:
            # older decide signature: decide(candle, history)
            return self.decide(candle, state)

    # --- end shim ---

    name = "ema_rsi_atr"

    def on_start(self, cfg: dict[str, Any], state: Any | None = None) -> None:
        self.cfg = cfg or {}
        s = (self.cfg.get("strategy") or {}) if isinstance(self.cfg, dict) else {}

        self.ema_fast = int(s.get("ema_fast", 12))
        self.ema_slow = int(s.get("ema_slow", 26))
        self.rsi_period = int(s.get("rsi_period", 14))
        self.atr_period = int(s.get("atr_period", 14))

        self.sl_atr_mult = float(s.get("sl_atr_mult", 1.5))
        self.tp_atr_mult = float(s.get("tp_atr_mult", 2.5))
        self.fallback_sl_pct = float(s.get("fallback_sl_pct", 0.01))
        self.fallback_tp_pct = float(s.get("fallback_tp_pct", 0.02))

        self.rsi_enter_max = float(s.get("rsi_enter_max", 70.0))
        self.rsi_exit_min = float(s.get("rsi_exit_min", 35.0))
        self.warmup = max(self.ema_slow + 2, self.rsi_period + 2, self.atr_period + 2)

    def on_tick(self, candle: Any, state: Any | None = None) -> None:
        return

    def decide(self, candle: Any, history: Any) -> Signal:
        hs: list[Any] = []
        try:
            if isinstance(history, list):
                hs = history
            elif isinstance(history, tuple):
                hs = list(history)
            else:
                hs = list(history)  # type: ignore[arg-type]
        except Exception:
            hs = []

        if candle is not None:
            hs = hs + [candle]

        closes = [_get(c, "close", 0.0) for c in hs if _get(c, "close", 0.0) > 0.0]
        highs = [_get(c, "high", 0.0) for c in hs if _get(c, "high", 0.0) > 0.0]
        lows = [_get(c, "low", 0.0) for c in hs if _get(c, "low", 0.0) > 0.0]

        if len(closes) < self.warmup:
            return Signal(
                action="hold",
                reason=f"warmup len={len(closes)} need>={self.warmup}",
                stop_loss=None,
                take_profit=None,
            )

        px = closes[-1]
        ef = _ema(closes[-(self.ema_fast * 4):], self.ema_fast)
        es = _ema(closes[-(self.ema_slow * 4):], self.ema_slow)
        r = _rsi(closes, self.rsi_period)
        a = _atr(highs, lows, closes, self.atr_period)

        if ef is None or es is None or r is None:
            return Signal(action="hold", reason="indicator_none", stop_loss=None, take_profit=None)

        if a is not None and a > 0.0:
            sl = px - (a * self.sl_atr_mult)
            tp = px + (a * self.tp_atr_mult)
        else:
            sl = px * (1.0 - self.fallback_sl_pct)
            tp = px * (1.0 + self.fallback_tp_pct)

        # long-sane
        if not (sl > 0.0) or sl >= px:
            sl = None
        if not (tp > 0.0) or tp <= px:
            tp = None

        if ef > es and r <= self.rsi_enter_max:
            return Signal(action="enter", reason="enter:ema_fast>slow,rsi_ok", stop_loss=sl, take_profit=tp)

        if ef < es or r <= self.rsi_exit_min:
            return Signal(action="exit", reason="exit:ema_cross_down_or_rsi_low", stop_loss=sl, take_profit=tp)

        return Signal(action="hold", reason="hold", stop_loss=sl, take_profit=tp)
