from __future__ import annotations

import os
import re

import shutil
import json
import subprocess
import secrets
import hashlib
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.templating import Jinja2Templates

TERMUX = bool(
    os.environ.get("TERMUX_VERSION") or "com.termux" in os.environ.get("PREFIX", "")
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

ENGINE_SERVICE = os.getenv("ALGONOVAX_ENGINE_SERVICE", "algonovax-engine.service")
KILLSWITCH_SERVICE = os.getenv(
    "ALGONOVAX_KILLSWITCH_SERVICE", "algonovax-killswitch.timer"
)
BACKTEST_SERVICE = os.getenv("ALGONOVAX_BACKTEST_SERVICE", "algonovax-backtest.service")

BASE = os.environ.get("ALGONOVAX_ROOT") or os.path.expanduser("~/AlgonovaX")
LOG_PATH = f"{BASE}/logs/engine.log"
OVERRIDE_FILE = os.path.join(
    os.path.expanduser("~"),
    ".config",
    "systemd",
    "user",
    f"{ENGINE_SERVICE}.d",
    "override.conf",
)

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

# Termux control scripts (no systemd)
ENGINE_START_SH = os.path.join(BASE, "scripts", "engine_start_termux.sh")
ENGINE_STOP_SH = os.path.join(BASE, "scripts", "engine_stop_termux.sh")
ENGINE_STATUS_SH = os.path.join(BASE, "scripts", "engine_status_termux.sh")
KILLSWITCH_ON_SH = os.path.join(BASE, "scripts", "kill_switch_on.sh")
KILLSWITCH_OFF_SH = os.path.join(BASE, "scripts", "kill_switch_off.sh")
KILLSWITCH_CHECK_SH = os.path.join(BASE, "scripts", "killswitch_check.sh")

ENGINE_PID_FILE = os.path.join(BASE, "var", "engine.pid")


def _exists_exec(path: str) -> bool:
    try:
        return os.path.exists(path) and os.access(path, os.X_OK)
    except Exception:
        return False


def _termux_engine_state() -> str:
    # Source of truth on Termux: scripts/engine_status_termux.sh
    try:
        if _exists_exec(ENGINE_STATUS_SH):
            out = _run([ENGINE_STATUS_SH])
            # expected: "RUNNING pid=..." or "STOPPED"
            if out.upper().startswith("RUNNING"):
                return "active"
            if out.upper().startswith("STOPPED"):
                return "inactive"
        # fallback: look for engine process names
        ps = subprocess.run(
            ["ps", "-ef"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        ).stdout
        if re.search(r"(engine_runner\.py|algonovax/engine|algonovax\.engine)", ps):
            return "active"
        return "inactive"
    except Exception:
        return "unknown"

def _termux_killswitch_state() -> str:
    # Soft/hard killswitch files are authoritative on Termux
    hard = os.path.exists(KS_HARD)
    soft = os.path.exists(KS_SOFT)
    if hard or soft:
        return "active"
    return "inactive"


def _termux_backtest_state() -> str:
    # No background unit on Termux; expose whether a job file exists
    try:
        return "active" if os.path.exists(BT_JOB_PATH) else "inactive"
    except Exception:
        return "unknown"


def _now() -> int:
    import time

    return int(time.time())


def _read_obj(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_obj(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _read_list(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run(cmd: list[str]) -> str:
    try:
        p = subprocess.run(
            cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        return p.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stdout or str(e))


def _systemctl(*args: str) -> str:
    # Termux/Android has no systemd/systemctl; emulate the subset we need using scripts/.
    if TERMUX or shutil.which("systemctl") is None:
        if not args:
            return "(termux) skip systemctl"
        action = args[0]
        unit = args[1] if len(args) > 1 else ""

        if "engine" in unit:
            if action in ("start", "enable"):
                return _run([ENGINE_START_SH]) if _exists_exec(ENGINE_START_SH) else "(termux) missing engine_start_termux.sh"
            if action in ("stop", "disable"):
                return _run([ENGINE_STOP_SH]) if _exists_exec(ENGINE_STOP_SH) else "(termux) missing engine_stop_termux.sh"
            if action == "restart":
                out1 = _run([ENGINE_STOP_SH]) if _exists_exec(ENGINE_STOP_SH) else ""
                out2 = _run([ENGINE_START_SH]) if _exists_exec(ENGINE_START_SH) else ""
                return (out1 + "\n" + out2).strip() or "(termux) restart attempted"
            if action == "is-active":
                return _termux_engine_state()

        if "killswitch" in unit:
            if action in ("start", "enable"):
                if _exists_exec(KILLSWITCH_ON_SH):
                    return _run([KILLSWITCH_ON_SH])
                _touch(KS_SOFT)
                return "(termux) killswitch on"
            if action in ("stop", "disable"):
                if _exists_exec(KILLSWITCH_OFF_SH):
                    return _run([KILLSWITCH_OFF_SH])
                _rm(KS_SOFT); _rm(KS_HARD)
                return "(termux) killswitch off"
            if action == "restart":
                if _exists_exec(KILLSWITCH_OFF_SH):
                    _run([KILLSWITCH_OFF_SH])
                if _exists_exec(KILLSWITCH_ON_SH):
                    return _run([KILLSWITCH_ON_SH])
                _touch(KS_SOFT)
                return "(termux) killswitch toggled"
            if action == "is-active":
                return "active" if os.path.exists(KS_SOFT) or os.path.exists(KS_HARD) else "inactive"

        return "(termux) skip systemctl"

    return _run(["systemctl", "--user", *args])



def _is_active(unit: str) -> str:
    # Termux/Android: no systemd. Provide best-effort states.
    if TERMUX:
        if "engine" in unit:
            return _termux_engine_state()
        if "killswitch" in unit:
            return _termux_killswitch_state()
        if "backtest" in unit:
            return _termux_backtest_state()
        return "unknown"
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a"):
        os.utime(path, None)


def _rm(path: str):
    if os.path.exists(path):
        os.remove(path)


def _hash_pin(pin: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 200_000)
    return h.hex()


def _auth_cfg() -> dict:
    return _read_obj(AUTH_PATH)


def _auth_enabled() -> bool:
    return bool(_auth_cfg().get("enabled", False))


def _session_ok(token: Optional[str]) -> bool:
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
    if not _auth_enabled():
        return
    token = request.cookies.get(COOKIE_NAME)
    if not _session_ok(token):
        raise HTTPException(status_code=401, detail="auth_required")


def _new_session() -> str:
    return secrets.token_urlsafe(32)


def _save_session(token: str):
    cfg = _auth_cfg()
    cfg.setdefault("sessions", {})
    cfg["sessions"][token] = {"exp": _now() + SESSION_TTL_SEC}
    _write_obj(AUTH_PATH, cfg)


def _write_engine_override(env: dict[str, str]) -> None:
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
    if _auth_enabled():
        token = request.cookies.get(COOKIE_NAME)
        if not _session_ok(token):
            return templates.TemplateResponse(
                "login.html", {"request": request, "enabled": True}
            )
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.post("/api/auth/setup")
def api_auth_setup(pin: str):
    pin = (pin or "").strip()
    if len(pin) < 4 or len(pin) > 12 or not pin.isdigit():
        raise HTTPException(status_code=400, detail="pin_must_be_4_to_12_digits")
    salt = secrets.token_bytes(16).hex()
    cfg = {
        "enabled": True,
        "salt": salt,
        "pin_hash": _hash_pin(pin, salt),
        "sessions": {},
    }
    _write_obj(AUTH_PATH, cfg)
    return {"ok": True}


@router.post("/api/auth/login")
def api_auth_login(pin: str):
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
        "override_file": (
            OVERRIDE_FILE if (not TERMUX and shutil.which("systemctl")) else None
        ),
        "intents_file": INTENTS_PATH,
    }


@router.post("/api/control/start")
def api_start(request: Request):
    _require_auth(request)
    _systemctl("start", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/control/stop")
def api_stop(request: Request):
    _require_auth(request)
    _systemctl("stop", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/control/restart")
def api_restart(request: Request):
    _require_auth(request)
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/control/recover")
def api_recover(request: Request):
    _require_auth(request)
    _systemctl("reset-failed", ENGINE_SERVICE)
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/panic")
def api_panic(request: Request):
    _require_auth(request)
    # immediate: create soft killswitch (engine will stop cleanly)
    _touch(KS_SOFT)
    return {"ok": True, "killswitch_soft_exists": True}


@router.post("/api/killswitch/soft/toggle")
def api_soft_toggle(request: Request):
    _require_auth(request)
    if os.path.exists(KS_SOFT):
        _rm(KS_SOFT)
    else:
        _touch(KS_SOFT)
    return {"ok": True, "killswitch_soft_exists": os.path.exists(KS_SOFT)}


@router.get("/api/strategies", response_class=JSONResponse)
def api_strategies(request: Request):
    _require_auth(request)
    return _read_obj(STRAT_PATH) or {"current": None, "available": []}


@router.post("/api/strategies/select", response_class=JSONResponse)
def api_strategy_select(request: Request, strategy: str):
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
    _require_auth(request)
    env = _read_engine_effective_env()
    return {k: env.get(k, "") for k in sorted(ALLOWED_ENV)}


@router.post("/api/settings/apply", response_class=JSONResponse)
def api_apply_settings(request: Request, settings: dict):
    _require_auth(request)
    sanitized: dict[str, str] = {}
    for k in ALLOWED_ENV:
        if k in settings:
            sanitized[k] = str(settings[k]).strip()

    if not sanitized.get("KILL_SWITCH_PATH"):
        sanitized["KILL_SWITCH_PATH"] = KS_HARD

    _write_engine_override(sanitized)
    _systemctl("daemon-reload")
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True, "applied": sanitized}


@router.post("/api/settings/mode/paper", response_class=JSONResponse)
def api_mode_paper(request: Request):
    _require_auth(request)
    env = _read_engine_effective_env()
    env.update(
        {
            "EXCHANGE": "paper",
            "PAPER_TRADING_ENABLED": "1",
            "LIVE_TRADING_ENABLED": "0",
            "KILL_SWITCH_PATH": KS_HARD,
        }
    )
    _write_engine_override({k: env.get(k, "") for k in ALLOWED_ENV})
    _systemctl("daemon-reload")
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/settings/mode/live", response_class=JSONResponse)
def api_mode_live(request: Request):
    _require_auth(request)
    # no safety theater: you must explicitly confirm by passing confirm=true
    return {"ok": False, "detail": "call /api/settings/mode/live/confirm?confirm=true"}


@router.post("/api/settings/mode/live/confirm", response_class=JSONResponse)
def api_mode_live_confirm(request: Request, confirm: bool = False):
    _require_auth(request)
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm=true required")
    env = _read_engine_effective_env()
    env.update(
        {
            "EXCHANGE": "kraken",
            "PAPER_TRADING_ENABLED": "0",
            "LIVE_TRADING_ENABLED": "1",
            "KILL_SWITCH_PATH": KS_HARD,
        }
    )
    _write_engine_override({k: env.get(k, "") for k in ALLOWED_ENV})
    _systemctl("daemon-reload")
    _systemctl("restart", ENGINE_SERVICE)
    return {"ok": True}


@router.post("/api/trade/buy", response_class=JSONResponse)
def api_trade_buy(request: Request, symbol: str, usd: float):
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
    _require_auth(request)
    strategy = (job.get("strategy") or "").strip()
    symbol = (job.get("symbol") or "").strip()
    timeframe = (job.get("timeframe") or "").strip()
    start = (job.get("start") or "").strip()
    end = (job.get("end") or "").strip()

    if not strategy or not symbol or not timeframe:
        raise HTTPException(
            status_code=400, detail="strategy_symbol_timeframe_required"
        )

    _write_obj(
        BT_JOB_PATH,
        {
            "strategy": strategy,
            "symbol": symbol,
            "timeframe": timeframe,
            "start": start,
            "end": end,
        },
    )
    _systemctl("start", BACKTEST_SERVICE)
    return {"ok": True}


@router.get("/api/backtest/output", response_class=PlainTextResponse)
def api_backtest_output(request: Request, tail: int = 300):
    _require_auth(request)
    tail = max(10, min(int(tail), 5000))
    if not os.path.exists(BT_OUT_PATH):
        return "(no backtest output yet)\n"
    return _run(["bash", "-lc", f"tail -n {tail} {BT_OUT_PATH}"])


@router.get("/api/config", response_class=JSONResponse)
def api_get_config(request: Request):
    _require_auth(request)
    return _read_obj(CFG_PATH)


@router.post("/api/config", response_class=JSONResponse)
def api_set_config(request: Request, cfg: dict):
    _require_auth(request)
    _write_obj(CFG_PATH, cfg)
    return {"ok": True}


@router.get("/api/balances", response_class=JSONResponse)
def api_balances(request: Request):
    _require_auth(request)
    return _read_obj(BAL_PATH)


@router.get("/api/positions", response_class=JSONResponse)
def api_positions(request: Request):
    _require_auth(request)
    return _read_list(POS_PATH)


@router.get("/api/trades", response_class=JSONResponse)
def api_trades(request: Request):
    _require_auth(request)
    return _read_list(TRD_PATH)


@router.get("/api/equity", response_class=JSONResponse)
def api_equity(request: Request):
    _require_auth(request)
    return _read_list(EQ_PATH)


@router.get("/api/logs", response_class=PlainTextResponse)
def api_logs(request: Request, tail: int = 200):
    _require_auth(request)
    tail = max(10, min(int(tail), 5000))
    if not os.path.exists(LOG_PATH):
        return "(log file not found)\n"
    return _run(["bash", "-lc", f"tail -n {tail} {LOG_PATH}"])
