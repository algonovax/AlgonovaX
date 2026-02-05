from __future__ import annotations
import threading

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


def run_once(settings: Settings) -> None:
    # Placeholder: wire your strategy/exchange here.
    log.info(
        f"tick exchange={settings.exchange} symbol={settings.symbol} timeframe={settings.timeframe}"
    )


def run_loop(settings: Settings, stop_evt: threading.Event | None = None) -> None:
    limits = RiskLimits(
        max_daily_loss_usd=settings.max_daily_loss_usd,
        max_open_positions=settings.max_open_positions,
        kill_switch_path=settings.kill_switch_path,
    )
    validate_limits(limits)

    log.info("engine_start")
    while True:
        if stop_evt is not None and stop_evt.is_set():
            try:
                log.info('engine_stop_requested')
            except Exception:
                pass
            return

        if _kill_switch_active(str(settings.kill_switch_path)):
            log.error("kill_switch_triggered; stopping")
            raise SystemExit(2)
        try:
            run_once(settings)
        except Exception:
            log.exception("engine_tick_failed")
        time.sleep(2)


def _kill_switch_active(kill_switch_path: str) -> bool:
    try:
        ks = Path(str(kill_switch_path))
        ks_soft = ks if str(ks).endswith("_SOFT") else Path(str(ks) + "_SOFT")
        return ks.exists() or ks_soft.exists()
    except Exception:
        return False

