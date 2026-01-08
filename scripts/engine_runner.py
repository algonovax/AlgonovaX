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
    """
    Return the filesystem path used as the kill switch file.
    
    Returns:
        kill_switch_path (str): Path from the `KILL_SWITCH_PATH` environment variable if set; otherwise the default path under the user's home directory: `~/projects/AlgonovaX/data/KILL_SWITCH` (with shell expansion applied).
    """
    return os.getenv("KILL_SWITCH_PATH", os.path.expanduser("~/projects/AlgonovaX/data/KILL_SWITCH"))

def _watch_kill_switch(stop_evt: threading.Event) -> None:
    # Hard stop even if run_loop is stuck or swallowing exceptions.
    """
    Monitor the filesystem for a kill-switch file and immediately terminate the process if it appears.
    
    This function runs a loop that periodically checks the path returned by `kill_switch_path()` and, if that file exists, performs a hard exit of the process with exit code 2.
    
    Parameters:
        stop_evt (threading.Event): Event used to request the watcher to stop; the loop exits when this event is set.
    """
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
    """
    Periodically logs a heartbeat message with timestamp, kill-switch path, and whether the kill-switch file exists until stopped.
    
    Parameters:
        stop_evt (threading.Event): Event that stops the heartbeat loop when set; the function waits 10 seconds between heartbeats.
    """
    while not stop_evt.is_set():
        try:
            ks = kill_switch_path()
            print(f"[engine] alive ts={int(time.time())} kill_switch={ks} exists={os.path.exists(ks)}", flush=True)
        except Exception:
            print("[engine] heartbeat error:", flush=True)
            traceback.print_exc()
        stop_evt.wait(10)

def main() -> int:
    """
    Start the engine runner: set up signal handlers and background watchdogs, load settings, process pending GUI buy/sell intents, and invoke the main run loop.
    
    Returns:
        int: `0` on clean shutdown, `2` if the kill-switch file was present at startup (early exit), `1` on unexpected error.
    """
    stop_evt = threading.Event()

    def _handle_signal(signum, frame):
        """
        Handle an incoming POSIX signal by logging it, triggering shutdown, and exiting.
        
        Parameters:
            signum (int): The signal number received.
            frame (types.FrameType | None): Execution frame at the time of the signal (as provided by the signal module).
        
        Raises:
            SystemExit: Always raised with exit code 0 after setting the shared shutdown event.
        """
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
    """
    Log a placeholder manual sell action without executing any trade.
    
    Parameters:
        symbol (str): Trading pair symbol (e.g., "BTC/USD").
        qty (float): Quantity of the base asset to sell.
    
    Notes:
        This function only prints a message indicating the sell was received and does not change balances, positions, or send orders.
    """
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
    """
    Read and parse JSON from a file path, returning a fallback on missing or invalid files.
    
    Parameters:
        path (str): Filesystem path to the JSON file.
        default (Any): Value to return if the file does not exist or cannot be read/parsed.
    
    Returns:
        Any: The decoded JSON object from the file, or `default` if the file is missing or an error occurs while reading or parsing.
    """
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _jwrite(path: str, obj: Any):
    """
    Write a JSON-serializable object to a file atomically, creating parent directories if needed.
    
    This function ensures the directory for `path` exists, writes `obj` as UTF-8 JSON (2-space indentation, keys sorted) to a temporary file, and then atomically replaces the target file with the temporary file to avoid partial writes.
    
    Parameters:
        path (str): Filesystem path to the target JSON file.
        obj (Any): JSON-serializable object to write.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
    os.replace(tmp, path)

def _now() -> int:
    """
    Current POSIX epoch time in seconds.
    
    Returns:
        int: The current time as the number of seconds since the Unix epoch.
    """
    return int(time.time())

def _split_symbol(symbol: str) -> tuple[str, str]:
    """
    Parse a trading symbol of the form 'BASE/QUOTE' and return the base and quote assets in uppercase.
    
    Parameters:
        symbol (str): Trading pair string expected to contain a single '/' separator (e.g., "BTC/USD").
    
    Returns:
        tuple[str, str]: A pair (base, quote) where both elements are trimmed and uppercased.
    
    Raises:
        ValueError: If `symbol` does not contain a '/' separator.
    """
    if "/" not in symbol:
        raise ValueError("symbol must look like BTC/USD")
    base, quote = symbol.split("/", 1)
    return base.strip().upper(), quote.strip().upper()

def _fetch_price_ccxt(symbol: str) -> float:
    """
    Fetches the latest market price for the given trading symbol from Kraken.
    
    Parameters:
        symbol (str): Exchange trading pair (e.g., "BTC/USD") accepted by ccxt/kraken.
    
    Returns:
        float: The last available trade/close price for the symbol.
    
    Raises:
        RuntimeError: If no positive price is available or if fetching the price fails.
    """
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
    """
    Initialize a paper trading wallet with a default USD balance if the provided wallet is empty.
    
    Parameters:
        bal (dict): Mapping of asset symbols to balances.
    
    Returns:
        dict: The original wallet if non-empty, otherwise a wallet initialized with {"USD": 10000.0}.
    """
    if not bal:
        bal = {"USD": 10000.0}
    return bal

def handle_manual_buy(symbol: str, usd: float) -> None:
    """
    Execute a paper-mode manual buy for a USD-quoted trading pair, updating local paper wallet, trades, and positions stored on disk.
    
    This function performs checks and side effects: it refuses to run if live trading is enabled, requires the symbol quote to be USD, fetches the current price, computes the purchased quantity from the provided USD amount, updates the on-disk balances, appends a trade record (capped to the last 2000 entries), and updates aggregated positions. Results and errors are printed to stdout.
    
    Parameters:
        symbol (str): Trading pair in the form "BASE/QUOTE" (e.g., "BTC/USD"). Quote must be "USD".
        usd (float): Amount in USD to spend on the buy.
    
    Returns:
        None
    """
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
    """
    Execute a manual paper-mode sell order for a USD-quoted trading pair and persist resulting balances, trades, and positions.
    
    Parameters:
        symbol (str): Trading pair in the form "BASE/QUOTE" (e.g., "BTC/USD"); quote must be USD.
        qty (float): Quantity of the base asset to sell.
    
    Behavior:
        - Refuses to run if live trading is enabled via the LIVE_TRADING_ENABLED environment variable.
        - Fetches a market price, converts the sold quantity to USD, updates the local wallet balances,
          appends a trade record (capped to the most recent 2000 entries), and adjusts positions.
        - Prints a success message on fill or an error message if an exception occurs.
    """
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
    """
    Prints a message to stdout while suppressing any printing errors.
    
    Attempts to print `msg` with `flush=True`; if printing raises an exception, the exception is ignored.
    Parameters:
        msg (str): The message to print.
    """
    try:
        print(msg, flush=True)
    except Exception:
        pass
# ========================================