from __future__ import annotations


from algonovax.intents import pop_new_intents
import os
import signal
import sys
import threading
import time
import traceback

from algonovax.config import load_settings
from algonovax.engine import run_loop

def kill_switch_path() -> str:
    return os.getenv("KILL_SWITCH_PATH", os.path.expanduser("~/projects/AlgonovaX/data/KILL_SWITCH"))

def _watch_kill_switch(stop_evt: threading.Event) -> None:
    # Hard stop even if run_loop is stuck or swallowing exceptions.
    while not stop_evt.is_set():
        try:
            ks = kill_switch_path()
            if os.path.exists(ks):
                print(f"[engine] kill_switch_triggered ({ks}); hard-exit", flush=True)
                os._exit(2)
        except Exception:
            print("[engine] kill-switch watcher error:", flush=True)
            traceback.print_exc()
        stop_evt.wait(0.5)

def _heartbeat(stop_evt: threading.Event) -> None:
    while not stop_evt.is_set():
        try:
            ks = kill_switch_path()
            print(f"[engine] alive ts={int(time.time())} kill_switch={ks} exists={os.path.exists(ks)}", flush=True)
        except Exception:
            print("[engine] heartbeat error:", flush=True)
            traceback.print_exc()
        stop_evt.wait(10)

def main() -> int:
    stop_evt = threading.Event()

    def _handle_signal(signum, frame):
        print(f"[engine] signal={signum} received; exiting", flush=True)
        stop_evt.set()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    ks = kill_switch_path()
    if os.path.exists(ks):
        print(f"[engine] kill switch ON at startup ({ks}); exiting cleanly", flush=True)
        return 2

    threading.Thread(target=_heartbeat, args=(stop_evt,), daemon=True).start()
    threading.Thread(target=_watch_kill_switch, args=(stop_evt,), daemon=True).start()

    try:
        print("[engine] starting", flush=True)
        settings = load_settings()
        print("[engine] settings loaded; entering run_loop()

        # --- GUI intents (BUY/SELL) ---
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
", flush=True)
        run_loop(settings)
        print("[engine] run_loop() returned; exiting cleanly", flush=True)
        return 0
    except SystemExit as e:
        code = int(getattr(e, "code", 0) or 0)
        print(f"[engine] SystemExit({code})", flush=True)
        return code
    except Exception:
        print("[engine] fatal:", flush=True)
        traceback.print_exc()
        return 1
    finally:
        stop_evt.set()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)


def handle_manual_buy(symbol: str, usd: float) -> None:
    # TODO: wire into your existing order/position logic
    print(f"[engine] handle_manual_buy not wired: {symbol} usd={usd}", flush=True)


def handle_manual_sell(symbol: str, qty: float) -> None:
    # TODO: wire into your existing order/position logic
    print(f"[engine] handle_manual_sell not wired: {symbol} qty={qty}", flush=True)

# =========================
# Manual trade execution (paper mode)
# =========================
from __future__ import annotations

import os
import json
import time
from typing import Any

_PAPER_BAL = os.path.expanduser("~/projects/AlgonovaX/data/balances.json")
_PAPER_TRD = os.path.expanduser("~/projects/AlgonovaX/data/trades.json")
_PAPER_POS = os.path.expanduser("~/projects/AlgonovaX/data/positions.json")

def _jread(path: str, default: Any):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _jwrite(path: str, obj: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    os.replace(tmp, path)

def _now() -> int:
    return int(time.time())

def _split_symbol(symbol: str) -> tuple[str, str]:
    if "/" not in symbol:
        raise ValueError("symbol must look like BTC/USD")
    base, quote = symbol.split("/", 1)
    return base.strip().upper(), quote.strip().upper()

def _fetch_price_ccxt(symbol: str) -> float:
    try:
        import ccxt  # type: ignore
        ex = ccxt.kraken({"enableRateLimit": True})
        t = ex.fetch_ticker(symbol)
        px = float(t.get("last") or t.get("close") or 0.0)
        if px <= 0:
            raise RuntimeError("no price")
        return px
    except Exception as e:
        raise RuntimeError(f"price_fetch_failed: {e}")

def _ensure_wallet(bal: dict) -> dict:
    # default paper wallet: $10,000 if empty
    if not bal:
        bal = {"USD": 10000.0}
    return bal

def handle_manual_buy(symbol: str, usd: float) -> None:
    try:
        if os.getenv("LIVE_TRADING_ENABLED", "0") == "1":
            print("[engine] REFUSE manual BUY: live trading enabled", flush=True)
            return

        base, quote = _split_symbol(symbol)
        if quote != "USD":
            print(f"[engine] REFUSE manual BUY: quote must be USD (got {quote})", flush=True)
            return

        px = _fetch_price_ccxt(symbol)
        qty = float(usd) / px

        bal = _ensure_wallet(_jread(_PAPER_BAL, {}))
        bal.setdefault("USD", 0.0)
        bal.setdefault(base, 0.0)

        if float(bal["USD"]) < float(usd):
            print(f"[engine] REFUSE manual BUY: insufficient USD balance={bal['USD']}", flush=True)
            return

        bal["USD"] = float(bal["USD"]) - float(usd)
        bal[base] = float(bal[base]) + float(qty)
        _jwrite(_PAPER_BAL, bal)

        tr = _jread(_PAPER_TRD, [])
        tr.append({"ts": _now(), "side": "BUY", "symbol": symbol, "price": px, "qty": qty, "usd": float(usd), "mode": "paper"})
        tr = tr[-2000:]
        _jwrite(_PAPER_TRD, tr)

        pos = _jread(_PAPER_POS, [])
        # simple position model: aggregate by base
        found = False
        for p in pos:
            if str(p.get("asset")).upper() == base:
                p["qty"] = float(p.get("qty", 0.0)) + float(qty)
                found = True
                break
        if not found:
            pos.append({"asset": base, "qty": float(qty)})
        _jwrite(_PAPER_POS, pos)

        print(f"[engine] paper BUY filled {symbol} qty={qty:.8f} px={px:.2f} usd={usd}", flush=True)
    except Exception as e:
        print(f"[engine] manual BUY error: {e}", flush=True)

def handle_manual_sell(symbol: str, qty: float) -> None:
    try:
        if os.getenv("LIVE_TRADING_ENABLED", "0") == "1":
            print("[engine] REFUSE manual SELL: live trading enabled", flush=True)
            return

        base, quote = _split_symbol(symbol)
        if quote != "USD":
            print(f"[engine] REFUSE manual SELL: quote must be USD (got {quote})", flush=True)
            return

        px = _fetch_price_ccxt(symbol)
        usd = float(qty) * px

        bal = _ensure_wallet(_jread(_PAPER_BAL, {}))
        bal.setdefault("USD", 0.0)
        bal.setdefault(base, 0.0)

        if float(bal[base]) < float(qty):
            print(f"[engine] REFUSE manual SELL: insufficient {base} balance={bal[base]}", flush=True)
            return

        bal[base] = float(bal[base]) - float(qty)
        bal["USD"] = float(bal["USD"]) + float(usd)
        _jwrite(_PAPER_BAL, bal)

        tr = _jread(_PAPER_TRD, [])
        tr.append({"ts": _now(), "side": "SELL", "symbol": symbol, "price": px, "qty": float(qty), "usd": usd, "mode": "paper"})
        tr = tr[-2000:]
        _jwrite(_PAPER_TRD, tr)

        pos = _jread(_PAPER_POS, [])
        for p in list(pos):
            if str(p.get("asset")).upper() == base:
                p["qty"] = float(p.get("qty", 0.0)) - float(qty)
                if p["qty"] <= 0:
                    pos.remove(p)
                break
        _jwrite(_PAPER_POS, pos)

        print(f"[engine] paper SELL filled {symbol} qty={qty:.8f} px={px:.2f} usd={usd:.2f}", flush=True)
    except Exception as e:
        print(f"[engine] manual SELL error: {e}", flush=True)

# ===== HOTFIX: repair broken log line =====
def _safe_print(msg: str):
    try:
        print(msg, flush=True)
    except Exception:
        pass
# ========================================
