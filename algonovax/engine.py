from __future__ import annotations

import logging
import time

from .config import Settings
from .risk import RiskLimits, kill_switch_triggered, validate_limits

log = logging.getLogger("algonovax.engine")

def run_once(settings: Settings) -> None:
    # Placeholder: wire your strategy/exchange here.
    log.info(f"tick exchange={settings.exchange} symbol={settings.symbol} timeframe={settings.timeframe}")

def run_loop(settings: Settings) -> None:
    limits = RiskLimits(
        max_daily_loss_usd=settings.max_daily_loss_usd,
        max_open_positions=settings.max_open_positions,
        kill_switch_path=settings.kill_switch_path,
    )
    validate_limits(limits)

    log.info("engine_start")
    while True:
        if kill_switch_triggered(limits.kill_switch_path):
            log.error("kill_switch_triggered; stopping")
            raise SystemExit(2)

        try:
            run_once(settings)
        except Exception:
            log.exception("engine_tick_failed")
        time.sleep(2)
