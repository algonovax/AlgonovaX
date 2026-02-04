from __future__ import annotations

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


def run_loop(settings: Settings) -> None:
    limits = RiskLimits(
        max_daily_loss_usd=settings.max_daily_loss_usd,
        max_open_positions=settings.max_open_positions,
        kill_switch_path=settings.kill_switch_path,
    )
    validate_limits(limits)

    log.info("engine_start")
    while True:
        if _kill_switch_active(str(settings.kill_switch_path)):
            log.error("kill_switch_triggered; stopping")
            raise SystemExit(2)
        try:
            run_once(settings)
        except Exception:
            log.exception("engine_tick_failed")
        time.sleep(2)


def _kill_switch_active(kill_switch_path: str) -> bool:
    """
    True iff the kill-switch file exists.
    Relative paths are resolved against current working directory.
    """
    try:
        from pathlib import Path

        ks = Path(str(kill_switch_path))
        if not ks.is_absolute():
            ks = (Path.cwd() / ks).resolve()
        return ks.exists()
    except Exception:
        return False
