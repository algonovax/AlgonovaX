from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_daily_loss_usd: float
    max_open_positions: int
    kill_switch_path: str


def kill_switch_triggered(path: str) -> bool:
    try:
        return os.path.exists(path)
    except Exception:
        return True  # fail closed


def validate_limits(limits: RiskLimits) -> None:
    if limits.max_daily_loss_usd <= 0:
        raise ValueError("MAX_DAILY_LOSS_USD must be > 0")
    if limits.max_open_positions <= 0:
        raise ValueError("MAX_OPEN_POSITIONS must be > 0")
