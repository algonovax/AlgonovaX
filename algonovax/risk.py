from __future__ import annotations

from pathlib import Path
from datetime import date
import json
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


# =========================
# PERSISTED RISK STATE
# =========================

@dataclass
class RiskState:
    day: str
    realized_pnl_usd: float
    open_positions: int


def _today_yyyy_mm_dd() -> str:
    return date.today().isoformat()


def load_state(path: str) -> RiskState:
    p = Path(path)
    if not p.exists():
        return RiskState(day=_today_yyyy_mm_dd(), realized_pnl_usd=0.0, open_positions=0)
    try:
        obj = json.loads(p.read_text("utf-8"))
        day_s = str(obj.get("day") or _today_yyyy_mm_dd())
        realized = float(obj.get("realized_pnl_usd") or 0.0)
        open_pos = int(obj.get("open_positions") or 0)
        return RiskState(day=day_s, realized_pnl_usd=realized, open_positions=open_pos)
    except Exception:
        # corrupt state -> reset safely
        return RiskState(day=_today_yyyy_mm_dd(), realized_pnl_usd=0.0, open_positions=0)


def save_state(path: str, st: RiskState) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(
        json.dumps(
            {"day": st.day, "realized_pnl_usd": st.realized_pnl_usd, "open_positions": st.open_positions},
            separators=(",", ":"),
        ),
        "utf-8",
    )
    tmp.replace(p)


def rollover_day_if_needed(st: RiskState) -> RiskState:
    today = _today_yyyy_mm_dd()
    if st.day != today:
        return RiskState(day=today, realized_pnl_usd=0.0, open_positions=0)
    return st


def record_realized_pnl(st: RiskState, delta_usd: float) -> RiskState:
    try:
        d = float(delta_usd)
    except Exception:
        d = 0.0
    return RiskState(day=st.day, realized_pnl_usd=st.realized_pnl_usd + d, open_positions=st.open_positions)


def set_open_positions(st: RiskState, n: int) -> RiskState:
    try:
        nn = int(n)
    except Exception:
        nn = st.open_positions
    return RiskState(day=st.day, realized_pnl_usd=st.realized_pnl_usd, open_positions=max(0, nn))


def enforce_state_limits(limits: "RiskLimits", st: RiskState, *, create_kill_switch: bool = True) -> None:
    # daily loss: realized_pnl_usd is negative when losing
    if st.realized_pnl_usd <= -abs(float(limits.max_daily_loss_usd)):
        if create_kill_switch:
            try:
                Path(limits.kill_switch_path).parent.mkdir(parents=True, exist_ok=True)
                Path(limits.kill_switch_path).write_text("risk:max_daily_loss_usd\n", "utf-8")
            except Exception:
                pass
        raise SystemExit(2)

    if st.open_positions > int(limits.max_open_positions):
        if create_kill_switch:
            try:
                Path(limits.kill_switch_path).parent.mkdir(parents=True, exist_ok=True)
                Path(limits.kill_switch_path).write_text("risk:max_open_positions\n", "utf-8")
            except Exception:
                pass
        raise SystemExit(2)
