from __future__ import annotations
import threading
from pathlib import Path

import logging
import sys
import time

from algonovax.config import Settings  # noqa: E402
from algonovax.risk import RiskLimits, validate_limits  # noqa: E402

# Deterministic logger: always emits to stdout (Termux + redirection safe)
log = logging.getLogger("algonovax.engine")
if not log.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(h)
log.setLevel(logging.INFO)


def run_once(settings, stop_evt=None) -> int:
    """Single tick.
    Back-compat: accepts (stop_evt, settings) if args are swapped.
    """
    try:
        if stop_evt is not None and hasattr(settings, "is_set") and not hasattr(stop_evt, "is_set"):
            settings, stop_evt = stop_evt, settings
    except Exception:
        pass



def run_loop(settings, stop_evt=None) -> int:

    # back-compat: tolerate swapped args (stop_evt, settings)
    try:
        if stop_evt is not None and hasattr(settings, "is_set") and not hasattr(stop_evt, "is_set"):
            settings, stop_evt = stop_evt, settings
    except Exception:
        pass

    # make stop_evt safe even if caller passes wrong type
    try:
        _stop_is_set = stop_evt.is_set  # type: ignore[attr-defined]
    except Exception:
        _stop_is_set = lambda: False

    """Main engine loop.
    Back-compat: accepts (stop_evt, settings) if args are swapped.
    """
    try:
        if stop_evt is not None and hasattr(settings, "is_set") and not hasattr(stop_evt, "is_set"):
            settings, stop_evt = stop_evt, settings
    except Exception:
        pass

    log.info("engine_start")
    while True:
        if stop_evt is not None and _stop_is_set():
            try:
                log.info('engine_stop_requested')
            except Exception:
                pass
            return

        if _kill_switch_active_hard_soft(str(settings.kill_switch_path)):
            log.error("kill_switch_triggered; stopping")
            raise SystemExit(2)
        try:
            run_once(settings)
        except Exception:
            log.exception("engine_tick_failed")
        time.sleep(2)

def _kill_switch_active_hard_soft(kill_switch_path: str) -> bool:
    try:
        ks = Path(str(kill_switch_path))
        ks_soft = ks if str(ks).endswith("_SOFT") else Path(str(ks) + "_SOFT")
        return ks.exists() or ks_soft.exists()
    except Exception:
        return False

def _kill_switch_active_hard_soft(kill_switch_path: str) -> bool:
    try:
        ks = Path(str(kill_switch_path))
        ks_soft = ks if str(ks).endswith("_SOFT") else Path(str(ks) + "_SOFT")
        return ks.exists() or ks_soft.exists()
    except Exception:
        return False

