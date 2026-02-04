from __future__ import annotations

import importlib
import os
import pkgutil
import signal
import threading
import time
import traceback
from typing import Any

# --- bootstrap (Termux-safe): ensure repo import works even if venv isn't activated ---
try:
    import os, sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    # Prefer venv site-packages if present (supports "python scripts/engine_runner.py")
    venv = repo / ".venv"
    if venv.exists():
        pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site = venv / "lib" / pyver / "site-packages"
        if site.exists() and str(site) not in sys.path:
            sys.path.insert(0, str(site))
    # Always include repo root for editable/local import
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
except Exception as _e:
    print(f"[engine] bootstrap failed: {_e}", flush=True)
# --- end bootstrap ---
from algonovax.config import load_settings
from algonovax.engine.engine import run_engine
from algonovax.intents import pop_new_intents

try:
    from algonovax.strategies._adapter import StrategyAdapter  # type: ignore
except Exception:
    StrategyAdapter = None  # type: ignore


def normalize_cfg(settings: Any) -> dict[str, Any]:
    if settings is None:
        return {}
    if isinstance(settings, dict):
        return settings

    md = getattr(settings, "model_dump", None)  # pydantic v2
    if callable(md):
        try:
            d = md()
            if isinstance(d, dict):
                return d
        except Exception:
            pass

    dd = getattr(settings, "dict", None)  # pydantic v1
    if callable(dd):
        try:
            d = dd()
            if isinstance(d, dict):
                return d
        except Exception:
            pass

    try:
        d = dict(getattr(settings, "__dict__", {}) or {})
        if isinstance(d, dict):
            return d
    except Exception:
        pass

    return {"_raw_settings": repr(settings)}


def kill_switch_path() -> str:
    root = os.environ.get("ALGONOVAX_ROOT") or os.path.expanduser("~/AlgonovaX")
    return os.getenv("KILL_SWITCH_PATH") or os.path.join(root, "data", "KILL_SWITCH")


def _watch_kill_switch(stop_evt: threading.Event) -> None:
    while not stop_evt.is_set():
        try:
            ks = kill_switch_path()
            if os.path.exists(ks):
                print(f"[engine] kill_switch_triggered ({ks}); hard-exit", flush=True)
                raise SystemExit(2)
        except Exception:
            print("[engine] kill-switch watcher error:", flush=True)
            traceback.print_exc()
        stop_evt.wait(0.5)


def _heartbeat(stop_evt: threading.Event) -> None:
    while not stop_evt.is_set():
        try:
            ks = kill_switch_path()
            print(
                f"[engine] alive ts={int(time.time())} kill_switch={ks} exists={os.path.exists(ks)}",
                flush=True,
            )
        except Exception:
            print("[engine] heartbeat error:", flush=True)
            traceback.print_exc()
        stop_evt.wait(10)


def resolve_strategy(cfg: dict[str, Any]):
    name = (
        os.environ.get("ALGONOVAX_STRATEGY")
        or cfg.get("strategy")
        or cfg.get("strategy_name")
        or ""
    ).strip()
    if not name:
        name = "ema_rsi_atr"

    # 1) registry, if it returns a usable object
    try:
        reg = importlib.import_module("algonovax.strategies.registry")
        for fn_name in ("get_strategy", "load", "create", "build"):
            fn = getattr(reg, fn_name, None)
            if callable(fn):
                try:
                    obj = fn(name)
                    if (
                        obj is not None
                        and hasattr(obj, "on_start")
                        and (
                            hasattr(obj, "on_candle")
                            or hasattr(obj, "decide")
                            or hasattr(obj, "on_tick")
                        )
                    ):
                        return obj
                except Exception:
                    pass
    except Exception:
        pass

    # 2) module candidates
    candidates: list[str] = []
    if "." in name:
        candidates.append(name)
    candidates.append(f"algonovax.strategies.{name}")

    # try class Strategy first
    last_err: Exception | None = None
    for mn in candidates:
        try:
            mod = importlib.import_module(mn)
            if hasattr(mod, "Strategy"):
                return mod.Strategy()
        except Exception as e:
            # TB_ON_RUNNER_FATAL

            last_err = e

    # function-style strategy -> adapt
    for mn in candidates:
        try:
            mod = importlib.import_module(mn)

            fn = None
            for fn_name in ("generate_signal", "decide", "signal", "get_signal"):
                cand = getattr(mod, fn_name, None)
                if callable(cand):
                    fn = cand
                    break
            if fn is None:
                continue

            if StrategyAdapter is not None:
                return StrategyAdapter(name=name, fn=fn)  # type: ignore

            class _LocalStrategy:
                def __init__(self):
                    self.name = name
                    self._rows: list[dict[str, Any]] = []
                    self._in_pos: bool = False
                    self._entry_index: int | None = None
                    self._entry_price: float | None = None

                def on_start(self, *_a, **_k):
                    return None

                def _to_row(self, candle: Any) -> dict[str, Any]:
                    c = (
                        candle
                        if isinstance(candle, dict)
                        else getattr(candle, "__dict__", {}) or {}
                    )
                    ts = (
                        c.get("ts") or c.get("timestamp") or c.get("time") or c.get("t")
                    )
                    return {
                        "ts": ts,
                        "open": float(c.get("open", c.get("o", 0.0)) or 0.0),
                        "high": float(c.get("high", c.get("h", 0.0)) or 0.0),
                        "low": float(c.get("low", c.get("l", 0.0)) or 0.0),
                        "close": float(c.get("close", c.get("c", 0.0)) or 0.0),
                        "volume": float(c.get("volume", c.get("v", 0.0)) or 0.0),
                    }

                def _signal_with_action(self, sig: Any):
                    if sig is None:
                        return None
                    if (
                        hasattr(sig, "action")
                        and hasattr(sig, "side")
                        and hasattr(sig, "stake_quote")
                    ):
                        return sig

                    def _get(obj: Any, key: str, default: Any = None) -> Any:
                        if obj is None:
                            return default
                        if isinstance(obj, dict):
                            return obj.get(key, default)
                        return getattr(obj, key, default)

                    raw_side = None
                    if isinstance(sig, str):
                        raw_side = sig
                    else:
                        raw_side = (
                            _get(sig, "side", None)
                            or _get(sig, "action", None)
                            or _get(sig, "signal", None)
                            or _get(sig, "type", None)
                        )

                    def _norm(x: Any) -> str:
                        x = str(x or "hold").strip().lower()
                        if "." in x:
                            x = x.split(".")[-1]
                        if x in ("hold", "buy", "sell"):
                            return x
                        if "buy" in x:
                            return "buy"
                        if "sell" in x:
                            return "sell"
                        return "hold"

                    class _Sig:
                        def __init__(self, side: Any, raw: Any):
                            self.side = _norm(side)
                            self.action = self.side
                            self.raw = raw

                            self.symbol = str(
                                _get(raw, "symbol", "") or _get(raw, "pair", "") or ""
                            )
                            self.price = float(_get(raw, "price", 0.0) or 0.0)
                            self.reason = str(_get(raw, "reason", "") or "")

                            self.stake_quote = float(
                                _get(raw, "stake_quote", 0.0)
                                or _get(raw, "usd", 0.0)
                                or 0.0
                            )
                            self.usd = float(_get(raw, "usd", self.stake_quote) or 0.0)
                            self.qty_base = float(
                                _get(raw, "qty_base", 0.0)
                                or _get(raw, "qty", 0.0)
                                or 0.0
                            )
                            self.qty = float(_get(raw, "qty", self.qty_base) or 0.0)

                            self.stop_loss = _get(raw, "stop_loss", None)
                            self.take_profit = _get(raw, "take_profit", None)
                            self.confidence = float(
                                _get(raw, "confidence", 0.0)
                                or _get(raw, "p", 0.0)
                                or 0.0
                            )

                    return _Sig(raw_side, sig)

                def _pos_from_state(self, state: Any) -> tuple[bool, float | None]:
                    try:
                        if state is None:
                            return False, None
                        if isinstance(state, dict):
                            # engine log shows pos_side/pos_entry, sometimes nested position
                            pos_side = str(state.get("pos_side", "") or "").lower()
                            pos_qty = float(state.get("pos_qty_base", 0.0) or 0.0)
                            pos_entry = state.get("pos_entry", None)
                            if pos_entry is None and isinstance(
                                state.get("position"), dict
                            ):
                                pos_entry = state["position"].get("entry_price", None)
                                pos_side = str(
                                    state["position"].get("side", pos_side) or ""
                                ).lower()
                                pos_qty = float(
                                    state["position"].get("qty_base", pos_qty) or 0.0
                                )
                            in_pos = (pos_qty > 0.0) or (pos_side in ("long", "buy"))
                            ep = float(pos_entry) if pos_entry is not None else None
                            if ep is not None and ep <= 0:
                                ep = None
                            return in_pos, ep

                        # object-like
                        pos_side = str(getattr(state, "pos_side", "") or "").lower()
                        pos_qty = float(getattr(state, "pos_qty_base", 0.0) or 0.0)
                        pos_entry = getattr(state, "pos_entry", None)
                        in_pos = (pos_qty > 0.0) or (pos_side in ("long", "buy"))
                        ep = float(pos_entry) if pos_entry is not None else None
                        if ep is not None and ep <= 0:
                            ep = None
                        return in_pos, ep
                    except Exception:
                        return False, None

                def on_candle(self, candle: Any, state: Any = None):
                    import pandas as pd

                    self._rows.append(self._to_row(candle))
                    if len(self._rows) > 2000:
                        self._rows = self._rows[-2000:]

                    df = pd.DataFrame(self._rows)
                    try:
                        if "ts" in df.columns:
                            df = df.sort_values("ts")
                    except Exception:
                        pass

                    # derive position state and persist entry_index on transition
                    in_pos, ep = self._pos_from_state(state)
                    if in_pos and not self._in_pos:
                        self._entry_index = len(df)  # df length at entry
                        self._entry_price = ep
                    if not in_pos:
                        self._entry_index = None
                        self._entry_price = None
                    self._in_pos = in_pos

                    termux_fast = os.environ.get("ALGONOVAX_TERMUX_FAST") == "1"

                    if termux_fast:
                        try:
                            out = fn(
                                df,
                                in_position=in_pos,
                                entry_price=self._entry_price,
                                entry_index=self._entry_index,
                                # make stub runs produce signals frequently
                                trend_ema=15,
                                fast_ema=5,
                                rsi_n=7,
                                rsi_entry=50.0,
                                atr_n=7,
                                impulse_atr=0.05,
                                min_atr_pct=0.0,
                                trend_slope_bars=1,
                                fast_slope_bars=1,
                                rsi_cross_lookback=2,
                                max_extension_atr=10.0,
                                min_pullback_atr=-10.0,
                                min_hold_bars=1,
                                max_hold_bars=18,
                            )
                        except TypeError:
                            # older signature (no kwargs)
                            out = fn(df)
                    else:
                        try:
                            out = fn(
                                df,
                                in_position=in_pos,
                                entry_price=self._entry_price,
                                entry_index=self._entry_index,
                            )
                        except TypeError:
                            out = fn(df)

                    return self._signal_with_action(out)

                def on_stop(self, *_a, **_k):
                    return None

            return _LocalStrategy()

        except Exception as e:
            last_err = e

    # 3) brute-force pick any Strategy class in algonovax.strategies
    try:
        pkg = importlib.import_module("algonovax.strategies")
        for m in pkgutil.iter_modules(pkg.__path__):
            if m.name.startswith("_"):
                continue
            mn = f"{pkg.__name__}.{m.name}"
            try:
                mod = importlib.import_module(mn)
                if hasattr(mod, "Strategy"):
                    print(f"[engine] strategy auto-picked: {m.name}", flush=True)
                    return mod.Strategy()
            except Exception:
                continue
    except Exception as e:
        last_err = last_err or e

    raise RuntimeError(
        f"No usable Strategy object found for '{name}'. last_err={last_err}"
    )


def handle_manual_buy(symbol: str, usd: float) -> None:
    print(f"[engine] handle_manual_buy not wired: {symbol} usd={usd}", flush=True)


def handle_manual_sell(symbol: str, qty: float) -> None:
    print(f"[engine] handle_manual_sell not wired: {symbol} qty={qty}", flush=True)


def main() -> int:
    stop_evt = threading.Event()

    def _handle_signal(signum, _frame):
        print(f"[engine] signal={signum} received; exiting", flush=True)
        stop_evt.set()
        return 0

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    threading.Thread(target=_heartbeat, args=(stop_evt,), daemon=True).start()

    try:
        print("[engine] starting", flush=True)
        settings = load_settings()
        cfg = normalize_cfg(settings)
        print("[engine] settings loaded; entering run_loop()", flush=True)

        # intents
        try:
            intents = pop_new_intents()
            for it in intents:
                t = (it.get("type") or "").upper()
                sym = (it.get("symbol") or "").strip()
                if not sym:
                    continue
                if t == "BUY":
                    usd = float(it.get("usd", 0) or 0)
                    if usd > 0:
                        print(f"[engine] intent BUY {sym} usd={usd}", flush=True)
                        handle_manual_buy(symbol=sym, usd=usd)
                elif t == "SELL":
                    qty = float(it.get("qty", 0) or 0)
                    if qty > 0:
                        print(f"[engine] intent SELL {sym} qty={qty}", flush=True)
                        handle_manual_sell(symbol=sym, qty=qty)
        except Exception as e:
            print(f"[engine] intent processing error: {e}", flush=True)

        # strategy resolution currently unused by the engine loop; removed.
        rc = run_engine(stop_evt)
        print(f"[engine] run_loop() returned rc={rc}", flush=True)
        return int(rc or 0)

    except SystemExit as e:
        code = int(getattr(e, "code", 0) or 0)
        print(f"[engine] SystemExit({code})", flush=True)
        return code
    except Exception:
        print("[engine] fatal:", flush=True)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
