from __future__ import annotations

import os
import json
import subprocess
import secrets
import hashlib
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

ENGINE_SERVICE = os.getenv("ALGONOVAX_ENGINE_SERVICE", "algonovax-engine.service")
KILLSWITCH_SERVICE = os.getenv("ALGONOVAX_KILLSWITCH_SERVICE", "algonovax-killswitch.timer")
BACKTEST_SERVICE = os.getenv("ALGONOVAX_BACKTEST_SERVICE", "algonovax-backtest.service")

BASE = os.path.expanduser("~/projects/AlgonovaX")
LOG_PATH = f"{BASE}/logs/engine.log"
KS_HARD = f"{BASE}/data/KILL_SWITCH"
KS_SOFT = f"{BASE}/data/KILL_SWITCH_SOFT"
LOCK_PATH = f"{BASE}/data/engine.lock"
CFG_PATH = f"{BASE}/config/runtime.json"
STRAT_PATH = f"{BASE}/config/strategies.json"

BAL_PATH = f"{BASE}/data/balances.json"
POS_PATH = f"{BASE}/data/positions.json"
TRD_PATH = f"{BASE}/data/trades.json"
EQ_PATH = f"{BASE}/data/equity.json"

BT_JOB_PATH = f"{BASE}/data/backtest_job.json"
BT_OUT_PATH = f"{BASE}/logs/backtests/backtest.out"

OVR_DIR = os.path.expanduser("~/.config/systemd/user/algonovax-engine.service.d")
OVR_FILE = os.path.join(OVR_DIR, "override.conf")

AUTH_PATH = f"{BASE}/config/auth.json"
COOKIE_NAME = "algonovax_session"
SESSION_TTL_SEC = 60 * 60 * 12  # 12h

ALLOWED_ENV = {
    "EXCHANGE",
    "PAPER_TRADING_ENABLED",
    "LIVE_TRADING_ENABLED",
    "SYMBOL",
    "TIMEFRAME",
    "MAX_DAILY_LOSS_USD",
    "MAX_OPEN_POSITIONS",
    "KILL_SWITCH_PATH",
}

# trade intents file (engine should watch this; if not, it's harmless)
INTENTS_PATH = f"{BASE}/data/intents.json"


def _now() -> int:
    """
    Return the current time as seconds since the Unix epoch.
    
    Returns:
        int: Current Unix epoch time rounded down to whole seconds.
    """
    import time
    return int(time.time())


def _read_obj(path: str) -> dict:
    """
    Read a JSON object from the given file path and return it as a dict.
    
    Parameters:
        path (str): Filesystem path to a JSON file.
    
    Returns:
        dict: Parsed JSON object; returns an empty dict if the file does not exist.
    """
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_obj(path: str, data: dict):
    """
    Write a dictionary to a file as pretty-printed JSON, creating parent directories if necessary.
    
    Parameters:
        path (str): Filesystem path of the JSON file to write.
        data (dict): Mapping to serialize to JSON; keys will be sorted and output formatted with two-space indentation.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _read_list(path: str):
    """
    Read a JSON array from a file, returning an empty list if the file does not exist.
    
    Parameters:
        path (str): Filesystem path to the JSON file.
    
    Returns:
        list: The parsed JSON list from the file, or an empty list if the file is missing.
    """
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run(cmd: list[str]) -> str:
    """
    Execute a command and return its trimmed standard output.
    
    Parameters:
        cmd (list[str]): Command and arguments to run (as passed to subprocess.run).
    
    Returns:
        str: The command's standard output with surrounding whitespace removed.
    
    Raises:
        HTTPException: With status 500 and the command's combined stdout/stderr (or the exception text) if the command exits with a non-zero status.
    """
    try:
        p = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return p.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stdout or str(e))


def _systemctl(*args: str) -> str:
    """
    Invoke `systemctl --user` with the provided arguments and return the command output.
    
    Returns:
        stdout (str): Standard output produced by the `systemctl` command.
    """
    return _run(["systemctl", "--user", *args])


def _is_active(unit: str) -> str:
    """
    Get the active state of a systemd user unit.
    
    Parameters:
        unit (str): Name of the systemd user unit to query.
    
    Returns:
        state (str): The unit state string as returned by `systemctl` (for example `active` or `inactive`), or `"unknown"` if the state cannot be determined.
    """
    try:
        return subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _touch(path: str):
    """
    Ensure a file exists and update its access and modification timestamps.
    
    Creates parent directories if necessary, creates the file if it does not exist, and updates its access/modify times to the current time.
    
    Parameters:
    	path (str): Filesystem path of the file to touch.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a"):
        os.utime(path, None)


def _rm(path: str):
    """
    Remove the filesystem entry at the given path if it exists.
    
    Parameters:
        path (str): Path to the file or directory to remove. Does nothing if the path does not exist.
    """
    if os.path.exists(path):
        os.remove(path)


def _hash_pin(pin: str, salt_hex: str) -> str:
    """
    Compute a PBKDF2-SHA256 hash of a PIN using a hex-encoded salt.
    
    Parameters:
        pin (str): The PIN to hash.
        salt_hex (str): Hex-encoded salt value.
    
    Returns:
        str: Hex-encoded derived key produced by PBKDF2-HMAC-SHA256.
    """
    salt = bytes.fromhex(salt_hex)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200_000)
    return h.hex()


def _auth_cfg() -> dict:
    """
    Load the authentication configuration from the predefined AUTH_PATH.
    
    Returns:
        dict: Authentication configuration dictionary; returns an empty dict if the file does not exist or cannot be read.
    """
    return _read_obj(AUTH_PATH)


def _auth_enabled() -> bool:
    """
    Indicates whether authentication is enabled in the stored authentication configuration.
    
    Returns:
        bool: `True` if authentication is enabled, `False` otherwise.
    """
    return bool(_auth_cfg().get("enabled", False))


def _session_ok(token: Optional[str]) -> bool:
    """
    Check whether a session token corresponds to an unexpired session.
    
    Parameters:
    	token (Optional[str]): Session token to validate.
    
    Returns:
    	bool: `True` if the token maps to a stored session with an expiry timestamp later than the current time, `False` otherwise.
    """
    if not token:
        return False
    cfg = _auth_cfg()
    sessions = cfg.get("sessions", {})
    rec = sessions.get(token)
    if not rec:
        return False
    exp = int(rec.get("exp", 0))
    return exp > _now()


def _require_auth(request: Request):
    """
    Enforces authentication for an incoming request by validating the session cookie.
    
    If authentication is enabled and the request does not contain a valid session token, raises an HTTPException with status code 401 and detail "auth_required".
    """
    if not _auth_enabled():
        return
    token = request.cookies.get(COOKIE_NAME)
    if not _session_ok(token):
        raise HTTPException(status_code=401, detail="auth_required")


def _new_session() -> str:
    """
    Generate a new URL-safe random token for session identification.
    
    Returns:
        token (str): A URL-safe random string suitable for use as a session identifier.
    """
    return secrets.token_urlsafe(32)


def _save_session(token: str):
    """
    Store a new session token with an expiration timestamp in the authentication configuration.
    
    Adds the provided token to the `sessions` map in the auth config with an `exp` value set to the current time plus SESSION_TTL_SEC, then persists the updated config to AUTH_PATH.
    
    Parameters:
    	token (str): Session token to save.
    """
    cfg = _auth_cfg()
    cfg.setdefault("sessions", {})
    cfg["sessions"][token] = {"exp": _now() + SESSION_TTL_SEC}
    _write_obj(AUTH_PATH, cfg)


def _write_engine_override(env: dict[str, str]) -> None:
    """
    Write the systemd override file that sets allowed environment variables for the engine service.
    
    Only keys present in ALLOWED_ENV are written; values are converted to strings with internal double quotes escaped. Ensures the override directory exists and replaces OVR_FILE with the new override content.
     
    Parameters:
        env (dict[str, str]): Mapping of environment variable names to values to apply.
    """
    os.makedirs(OVR_DIR, exist_ok=True)
    lines = ["[Service]"]
    for k, v in env.items():
        if k not in ALLOWED_ENV:
            continue
        v = str(v).replace('"', '\\"')
        lines.append(f'Environment={k}="{v}"')
    with open(OVR_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _read_engine_effective_env() -> dict:
    """
    Retrieve the effective Environment variables for the engine systemd unit.
    
    Parses the output of `systemctl --user show <ENGINE_SERVICE> --property=Environment` and returns a mapping of environment variable names to their values. Quoted values will have surrounding quotes removed. If no Environment is set or an error occurs, returns an empty dict.
    
    Returns:
        dict: Mapping of environment variable names to values; empty if none or on error.
    """
    try:
        out = subprocess.run(
            ["systemctl", "--user", "show", ENGINE_SERVICE, "--property=Environment"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ).stdout.strip()
        if not out.startswith("Environment="):
            return {}
        raw = out.split("=", 1)[1].strip()
        if not raw:
            return {}
        parts = raw.split()
        env = {}
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                env[k] = v.strip('"')
        return env
    except Exception:
        return {}


def _append_intent(intent: dict):
    """
    Append a trading intent to the persisted intents file, timestamp it, and trim stored intents to the most recent 200.
    
    The function copies the provided intent, adds a `ts` field with the current epoch time (seconds), ensures the on-disk structure contains an "intents" list, appends the new intent, trims the list to the last 200 entries, and writes the result to INTENTS_PATH.
    
    Parameters:
        intent (dict): Intent payload to record. Must be JSON-serializable; the function will copy and augment it with a `ts` timestamp.
    """
    cur = _read_obj(INTENTS_PATH) or {"intents": []}
    cur.setdefault("intents", [])
    intent = dict(intent)
    intent["ts"] = _now()
    cur["intents"].append(intent)
    # cap file size
    cur["intents"] = cur["intents"][-200:]
    _write_obj(INTENTS_PATH, cur)


@router.get("/ui", response_class=HTMLResponse)
def ui_home(request: Request):
    """
    Render the UI home page, enforcing authentication when enabled.
    
    Returns:
        TemplateResponse: The login page when authentication is enabled and the session is missing or invalid; otherwise the dashboard page.
    """
    if _auth_enabled():
        token = request.cookies.get(COOKIE_NAME)
        if not _session_ok(token):
            return templates.TemplateResponse("login.html", {"request": request, "enabled": True})
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.post("/api/auth/setup")
def api_auth_setup(pin: str):
    """
    Initializes authentication by creating a PIN-based admin account.
    
    Validates that `pin` is 4 to 12 digits long. On success writes an authentication configuration
    (enables auth, stores a generated salt, the hashed PIN, and an empty sessions map) to the auth file.
    
    Parameters:
    	pin (str): The numeric PIN to set for admin login; must be 4–12 digits.
    
    Returns:
    	dict: `{"ok": True}` on success.
    
    Raises:
    	HTTPException: If `pin` is not 4 to 12 digits (status 400, detail "pin_must_be_4_to_12_digits").
    """
    pin = (pin or "").strip()
    if len(pin) < 4 or len(pin) > 12 or not pin.isdigit():
        raise HTTPException(status_code=400, detail="pin_must_be_4_to_12_digits")
    salt = secrets.token_bytes(16).hex()
    cfg = {"enabled": True, "salt": salt, "pin_hash": _hash_pin(pin, salt), "sessions": {}}
    _write_obj(AUTH_PATH, cfg)
    return {"ok": True}


@router.post("/api/auth/login")
def api_auth_login(pin: str):
    """
    Authenticate the provided PIN and establish a session by setting a session cookie and redirecting to the UI.
    
    Parameters:
        pin (str): The PIN provided by the user.
    
    Returns:
        RedirectResponse: An HTTP redirect to "/ui" with a session cookie set on successful authentication.
    
    Raises:
        HTTPException: 400 if authentication is not enabled.
        HTTPException: 500 if authentication is misconfigured.
        HTTPException: 401 if the PIN is invalid.
    """
    cfg = _auth_cfg()
    if not cfg.get("enabled"):
        raise HTTPException(status_code=400, detail="auth_not_enabled")
    salt = cfg.get("salt")
    pin_hash = cfg.get("pin_hash")
    if not salt or not pin_hash:
        raise HTTPException(status_code=500, detail="auth_misconfigured")
    if _hash_pin((pin or "").strip(), salt) != pin_hash:
        raise HTTPException(status_code=401, detail="bad_pin")

    token = _new_session()
    _save_session(token)

    resp = RedirectResponse(url="/ui", status_code=303)
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
    return resp


@router.post("/api/auth/logout")
def api_auth_logout(request: Request):
    """
    Log out the current session and redirect the client to the UI home page.
    
    If a session token cookie is present and recorded in the auth configuration, remove that session entry from persistent storage. The returned response clears the session cookie on the client and issues a 303 redirect to /ui.
    
    Returns:
        RedirectResponse: Response redirecting to /ui with the session cookie deleted.
    """
    cfg = _auth_cfg()
    token = request.cookies.get(COOKIE_NAME)
    if token and cfg.get("sessions", {}).get(token):
        cfg["sessions"].pop(token, None)
        _write_obj(AUTH_PATH, cfg)
    resp = RedirectResponse(url="/ui", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@router.get("/api/status", response_class=JSONResponse)
def api_status(request: Request):
    """
    Return runtime status information about the engine, services, killswitches, and relevant file paths.
    
    Returns:
        status (dict): Mapping with the following keys:
            - `engine`: `"active"`, `"inactive"`, or `"unknown"` for the engine service state.
            - `killswitch`: `"active"`, `"inactive"`, or `"unknown"` for the killswitch service state.
            - `backtest`: `"active"`, `"inactive"`, or `"unknown"` for the backtest service state.
            - `killswitch_hard_exists` (bool): `True` if the hard killswitch file exists.
            - `killswitch_soft_exists` (bool): `True` if the soft killswitch file exists.
            - `engine_lock_exists` (bool): `True` if the engine lock file exists.
            - `log_path` (str): Filesystem path to the engine log file.
            - `auth_enabled` (bool): `True` if authentication is enabled.
            - `override_file` (str): Filesystem path to the engine systemd override file.
            - `intents_file` (str): Filesystem path to the intents (trade actions) file.
    """
    _require_auth(request)
    return {
        "engine": _is_active(ENGINE_SERVICE),
        "killswitch": _is_active(KILLSWITCH_SERVICE),
        "backtest": _is_active(BACKTEST_SERVICE),
        "killswitch_hard_exists": os.path.exists(KS_HARD),
        "killswitch_soft_exists": os.path.exists(KS_SOFT),
        "engine_lock_exists": os.path.exists(LOCK_PATH),
        "log_path": LOG_PATH,
        "auth_enabled": _auth_enabled(),
        "override_file": OVR_FILE,
        "intents_file": INTENTS_PATH,
    }


@router.post("/api/control/start")
def api_start(request: Request):
    """
    Start the configured engine service.
    
    Returns:
        result (dict): `{"ok": True}` on success.
    """
    _require_auth(request)
    _systemctl("start", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/control/stop")
def api_stop(request: Request):
    """
    Stop the configured engine service.
    
    Parameters:
        request (Request): Incoming HTTP request; used to enforce authentication before performing the stop.
    
    Returns:
        dict: Confirmation object `{'ok': True}` when the stop command is issued.
    """
    _require_auth(request)
    _systemctl("stop", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/control/restart")
def api_restart(request: Request):
    """
    Restart the engine systemd service; requires a valid authenticated session.
    
    Returns:
        dict: A dictionary with `ok` set to `True` on successful restart.
    """
    _require_auth(request)
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/control/recover")
def api_recover(request: Request):
    """
    Reset the engine service by clearing any failed state and restarting the engine.
    
    Returns:
        dict: `{"ok": True}` on success.
    """
    _require_auth(request)
    _systemctl("reset-failed", ENGINE_SERVICE)
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/panic")
def api_panic(request: Request):
    """
    Create a soft killswitch file to request a clean engine stop.
    
    Creates (or updates) the soft killswitch file so the engine will stop cleanly and returns the resulting status.
    
    Returns:
        dict: {"ok": True, "killswitch_soft_exists": True} indicating the soft killswitch file now exists.
    """
    _require_auth(request)
    # immediate: create soft killswitch (engine will stop cleanly)
    _touch(KS_SOFT)
    return {"ok": True, "killswitch_soft_exists": True}


@router.post("/api/killswitch/soft/toggle")
def api_soft_toggle(request: Request):
    """
    Toggle the soft killswitch file presence.
    
    Returns:
        dict: `{'ok': True, 'killswitch_soft_exists': <bool>}` where `killswitch_soft_exists` is `True` if the soft killswitch file exists after the toggle, `False` otherwise.
    """
    _require_auth(request)
    if os.path.exists(KS_SOFT):
        _rm(KS_SOFT)
    else:
        _touch(KS_SOFT)
    return {"ok": True, "killswitch_soft_exists": os.path.exists(KS_SOFT)}


@router.get("/api/strategies", response_class=JSONResponse)
def api_strategies(request: Request):
    """
    Retrieve the current strategy selection and the list of available strategies.
    
    Returns:
        dict: Mapping with keys:
            - "current": the name of the selected strategy or None
            - "available": list of available strategy names
    
    Raises:
        HTTPException: 401 if the request is not authenticated.
    """
    _require_auth(request)
    return _read_obj(STRAT_PATH) or {"current": None, "available": []}


@router.post("/api/strategies/select", response_class=JSONResponse)
def api_strategy_select(request: Request, strategy: str):
    """
    Set the current trading strategy to one of the available strategies and restart the engine.
    
    Parameters:
        strategy (str): Name of the strategy to select; must be present in the available strategies list.
    
    Returns:
        dict: {"ok": True, "current": strategy} confirming the applied strategy.
    
    Raises:
        HTTPException: 400 with detail "unknown_strategy" if the provided strategy is not available.
        HTTPException: 401 if the request is not authenticated.
    """
    _require_auth(request)
    strategy = (strategy or "").strip()
    data = _read_obj(STRAT_PATH)
    avail = data.get("available", [])
    if strategy not in avail:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    data["current"] = strategy
    _write_obj(STRAT_PATH, data)

    cfg = _read_obj(CFG_PATH)
    cfg["STRATEGY"] = strategy
    _write_obj(CFG_PATH, cfg)

    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True, "current": strategy}


@router.get("/api/settings", response_class=JSONResponse)
def api_get_settings(request: Request):
    """
    Return the engine's effective environment filtered to the configured allowed keys.
    
    Returns:
        dict: Mapping of each allowed environment variable name to its effective value; variables not present are returned as an empty string.
    """
    _require_auth(request)
    env = _read_engine_effective_env()
    return {k: env.get(k, "") for k in sorted(ALLOWED_ENV)}


@router.post("/api/settings/apply", response_class=JSONResponse)
def api_apply_settings(request: Request, settings: dict):
    """
    Apply and persist engine environment overrides from the provided settings.
    
    Filters the given `settings` to the allowed environment keys, coerces each value to a trimmed string, ensures `KILL_SWITCH_PATH` is set (defaults to KS_SOFT if absent), writes the resulting environment override for the engine, reloads the systemd user daemon, and restarts the engine service.
    
    Parameters:
        settings (dict): Mapping of environment keys to values; only keys in ALLOWED_ENV are applied.
    
    Returns:
        dict: `{"ok": True, "applied": sanitized}` where `sanitized` is the final map of applied environment variables.
    """
    _require_auth(request)
    sanitized: dict[str, str] = {}
    for k in ALLOWED_ENV:
        if k in settings:
            sanitized[k] = str(settings[k]).strip()

    if not sanitized.get("KILL_SWITCH_PATH"):
        sanitized["KILL_SWITCH_PATH"] = KS_SOFT

    _write_engine_override(sanitized)
    _systemctl("daemon-reload")
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True, "applied": sanitized}


@router.post("/api/settings/mode/paper", response_class=JSONResponse)
def api_mode_paper(request: Request):
    """
    Switches the engine to paper-trading mode.
    
    Sets the effective engine environment to enable paper trading, writes the allowed environment overrides, reloads the systemd user daemon, and restarts the engine service.
    
    Returns:
        dict: `{"ok": True}` on success.
    """
    _require_auth(request)
    env = _read_engine_effective_env()
    env.update(
        {
            "EXCHANGE": "paper",
            "PAPER_TRADING_ENABLED": "1",
            "LIVE_TRADING_ENABLED": "0",
            "KILL_SWITCH_PATH": KS_SOFT,
        }
    )
    _write_engine_override({k: env.get(k, "") for k in ALLOWED_ENV})
    _systemctl("daemon-reload")
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/settings/mode/live", response_class=JSONResponse)
def api_mode_live(request: Request):
    """
    Require explicit confirmation before switching the engine to live trading mode.
    
    This endpoint enforces authentication and returns an instruction directing the caller to the confirmation endpoint; it does not change any settings itself.
    
    Returns:
    	A JSON object with `ok` set to `False` and `detail` containing the instruction string "call /api/settings/mode/live/confirm?confirm=true".
    """
    _require_auth(request)
    # no safety theater: you must explicitly confirm by passing confirm=true
    return {"ok": False, "detail": "call /api/settings/mode/live/confirm?confirm=true"}


@router.post("/api/settings/mode/live/confirm", response_class=JSONResponse)
def api_mode_live_confirm(request: Request, confirm: bool = False):
    """
    Switches the engine to live Kraken trading mode and applies the corresponding environment override.
    
    Requires an authenticated session; if `confirm` is not `True` a 400 HTTP error is raised. This call writes the allowed environment keys with live-mode values (including enabling live trading, disabling paper trading, setting EXCHANGE to "kraken", and pointing KILL_SWITCH_PATH to the soft killswitch), reloads systemd user daemon, and restarts the engine service.
    
    Parameters:
        confirm (bool): Must be `True` to proceed; prevents accidental activation of live trading.
    
    Returns:
        dict: {"ok": True} on success.
    """
    _require_auth(request)
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm=true required")
    env = _read_engine_effective_env()
    env.update(
        {
            "EXCHANGE": "kraken",
            "PAPER_TRADING_ENABLED": "0",
            "LIVE_TRADING_ENABLED": "1",
            "KILL_SWITCH_PATH": KS_SOFT,
        }
    )
    _write_engine_override({k: env.get(k, "") for k in ALLOWED_ENV})
    _systemctl("daemon-reload")
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/trade/buy", response_class=JSONResponse)
def api_trade_buy(request: Request, symbol: str, usd: float):
    """
    Create and record a BUY trade intent for a given trading symbol and USD amount.
    
    Symbol must be a non-empty string. USD must be greater than 0 and at most 10,000,000. Requires an authenticated session.
    
    Parameters:
        symbol (str): Trading symbol to buy.
        usd (float): USD amount to spend for the buy.
    
    Returns:
        dict: `{"ok": True}` on success.
    """
    _require_auth(request)
    if usd <= 0 or usd > 10_000_000:
        raise HTTPException(status_code=400, detail="bad_usd")
    symbol = (symbol or "").strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="bad_symbol")
    _append_intent({"type": "BUY", "symbol": symbol, "usd": float(usd)})
    return {"ok": True}


@router.post("/api/trade/sell", response_class=JSONResponse)
def api_trade_sell(request: Request, symbol: str, qty: float):
    """
    Create a sell intent for the given symbol and quantity.
    
    Parameters:
        request (Request): Incoming HTTP request (used for authentication).
        symbol (str): Asset symbol to sell.
        qty (float): Quantity of the asset to sell (must be greater than 0 and at most 10,000,000).
    
    Returns:
        dict: `{"ok": True}` on success.
    
    Raises:
        HTTPException: 400 with detail "bad_qty" if `qty` is out of range.
        HTTPException: 400 with detail "bad_symbol" if `symbol` is empty.
    """
    _require_auth(request)
    if qty <= 0 or qty > 10_000_000:
        raise HTTPException(status_code=400, detail="bad_qty")
    symbol = (symbol or "").strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="bad_symbol")
    _append_intent({"type": "SELL", "symbol": symbol, "qty": float(qty)})
    return {"ok": True}


@router.post("/api/backtest/run", response_class=JSONResponse)
def api_backtest_run(request: Request, job: dict):
    """
    Schedule and start a backtest using the provided job specification.
    
    Parameters:
        job (dict): Backtest job fields. Required keys: `"strategy"`, `"symbol"`, and `"timeframe"` (all non-empty strings). Optional keys: `"start"` and `"end"` (date/time strings or empty).
    
    Returns:
        dict: `{"ok": True}` on success.
    
    Raises:
        HTTPException: 400 if `strategy`, `symbol`, or `timeframe` is missing or empty; 401 if the request is not authenticated.
    """
    _require_auth(request)
    strategy = (job.get("strategy") or "").strip()
    symbol = (job.get("symbol") or "").strip()
    timeframe = (job.get("timeframe") or "").strip()
    start = (job.get("start") or "").strip()
    end = (job.get("end") or "").strip()

    if not strategy or not symbol or not timeframe:
        raise HTTPException(status_code=400, detail="strategy_symbol_timeframe_required")

    _write_obj(BT_JOB_PATH, {"strategy": strategy, "symbol": symbol, "timeframe": timeframe, "start": start, "end": end})
    _systemctl("start", BACKTEST_SERVICE)
    return {"ok": True}


@router.get("/api/backtest/output", response_class=PlainTextResponse)
def api_backtest_output(request: Request, tail: int = 300):
    """
    Return the last lines of the backtest output log.
    
    Requires the incoming request to be authenticated.
    
    Parameters:
    	request (Request): Incoming HTTP request; used for authentication enforcement.
    	tail (int): Number of lines to return from the end of the backtest output; clamped to the range 10–5000.
    
    Returns:
    	str: The requested tail of the backtest output file, or "(no backtest output yet)\n" if the output file does not exist.
    """
    _require_auth(request)
    tail = max(10, min(int(tail), 5000))
    if not os.path.exists(BT_OUT_PATH):
        return "(no backtest output yet)\n"
    return _run(["bash", "-lc", f"tail -n {tail} {BT_OUT_PATH}"])


@router.get("/api/config", response_class=JSONResponse)
def api_get_config(request: Request):
    """
    Return the runtime configuration read from disk, enforcing authentication.
    
    Returns:
        dict: Configuration object loaded from CFG_PATH; returns an empty dict if the config file is missing or unreadable.
    """
    _require_auth(request)
    return _read_obj(CFG_PATH)


@router.post("/api/config", response_class=JSONResponse)
def api_set_config(request: Request, cfg: dict):
    """
    Persist the given configuration mapping to the runtime config file.
    
    Parameters:
        cfg (dict): Configuration mapping to write to the runtime config path.
    
    Returns:
        dict: `{'ok': True}` on success.
    """
    _require_auth(request)
    _write_obj(CFG_PATH, cfg)
    return {"ok": True}


@router.get("/api/balances", response_class=JSONResponse)
def api_balances(request: Request):
    """
    Retrieve current account balances from the balances file.
    
    Returns:
        balances (dict): Parsed JSON object from BAL_PATH containing stored account balances.
    """
    _require_auth(request)
    return _read_obj(BAL_PATH)


@router.get("/api/positions", response_class=JSONResponse)
def api_positions(request: Request):
    """
    Return stored trading positions.
    
    Returns:
        list: Positions loaded from the positions file at POS_PATH, or an empty list if the file is missing.
    """
    _require_auth(request)
    return _read_list(POS_PATH)


@router.get("/api/trades", response_class=JSONResponse)
def api_trades(request: Request):
    """
    Return the recorded trades from persistent storage.
    
    Reads and returns the JSON list stored at TRD_PATH representing recorded trade records.
    
    Returns:
        list: List of trade objects read from TRD_PATH (empty list if the file is missing).
    """
    _require_auth(request)
    return _read_list(TRD_PATH)


@router.get("/api/equity", response_class=JSONResponse)
def api_equity(request: Request):
    """
    Retrieve the stored equity time series for the engine.
    
    Requires a valid authenticated session.
    
    Returns:
        list: Equity records loaded from the equity data file; an empty list if the file does not exist.
    """
    _require_auth(request)
    return _read_list(EQ_PATH)


@router.get("/api/logs", response_class=PlainTextResponse)
def api_logs(request: Request, tail: int = 200):
    """
    Return the last N lines of the application's log file.
    
    Clamps `tail` to an integer between 10 and 5000. If the log file is missing, returns "(log file not found)\n".
    
    Parameters:
        tail (int): Number of lines to retrieve; values less than 10 are treated as 10, values greater than 5000 as 5000.
    
    Returns:
        str: The tailed log content or "(log file not found)\n" when the log file does not exist.
    """
    _require_auth(request)
    tail = max(10, min(int(tail), 5000))
    if not os.path.exists(LOG_PATH):
        return "(log file not found)\n"
    return _run(["bash", "-lc", f"tail -n {tail} {LOG_PATH}"])