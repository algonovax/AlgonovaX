from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from algonovax.config import Settings

log = logging.getLogger("algonovax.engine")
if not log.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(h)
log.setLevel(logging.INFO)

STATE_PATH = Path("data/state.json")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _kill_switch_active_hard_soft(kill_switch_path: str) -> bool:
    try:
        ks = Path(str(kill_switch_path))
        ks_soft = ks if str(ks).endswith("_SOFT") else Path(str(ks) + "_SOFT")
        return ks.exists() or ks_soft.exists()
    except Exception:
        return False


def run_once(settings: Settings, stop_evt: threading.Event | None = None) -> int:
    # tolerate swapped args (stop_evt, settings)
    try:
        if stop_evt is not None and hasattr(settings, "is_set") and not hasattr(stop_evt, "is_set"):
            settings, stop_evt = stop_evt, settings  # type: ignore[assignment]
    except Exception:
        pass

    payload: dict[str, Any] = {
        "ts": _utc_now_iso(),
        "exchange": getattr(settings, "exchange", None),
        "symbol": getattr(settings, "symbol", None),
        "timeframe": getattr(settings, "timeframe", None),
        "pid": os.getpid(),
        "ok": True,
    }

    try:
        _atomic_write_json(STATE_PATH, payload)
    except Exception as e:
        log.error("state_write_failed err=%r", e)
        payload["ok"] = False
        payload["err"] = repr(e)

    log.info(
        "tick exchange=%s symbol=%s timeframe=%s ok=%s",
        payload.get("exchange"),
        payload.get("symbol"),
        payload.get("timeframe"),
        payload.get("ok"),
    )
    return 0


def run_loop(settings: Settings, stop_evt: threading.Event | None = None) -> int:
    # tolerate swapped args (stop_evt, settings)
    try:
        if stop_evt is not None and hasattr(settings, "is_set") and not hasattr(stop_evt, "is_set"):
            settings, stop_evt = stop_evt, settings  # type: ignore[assignment]
    except Exception:
        pass

    try:
        _stop_is_set = stop_evt.is_set  # type: ignore[attr-defined]
    except Exception:
        _stop_is_set = lambda: False

    log.info("engine_start")
    while True:
        if stop_evt is not None and _stop_is_set():
            log.info("engine_stop_requested")
            return 0

        if _kill_switch_active_hard_soft(str(settings.kill_switch_path)):
            log.error("kill_switch_triggered; stopping")
            raise SystemExit(2)

        try:
            run_once(settings, stop_evt)
        except Exception:
            log.exception("engine_tick_failed")

        time.sleep(2)
