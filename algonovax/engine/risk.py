from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Tuple

@dataclass
class RiskConfig:
    max_position_pct: float
    max_risk_pct: float
    max_daily_drawdown_pct: float

class RiskEngine:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg

    def validate_intent(self, intent: Any, st: Any) -> Tuple[bool, str]:
        action = getattr(intent, "action", None)
        if action == "hold":
            return True, "ok"

        # daily drawdown gate
        if st.day_start_equity > 0:
            dd = (st.day_start_equity - st.equity) / st.day_start_equity
            if dd >= self.cfg.max_daily_drawdown_pct:
                return False, f"daily_drawdown_block dd={dd:.4f} limit={self.cfg.max_daily_drawdown_pct:.4f}"

        # only allow enter if flat; allow exit if long
        if action == "enter":
            if st.position.side != "flat":
                return False, "already_in_position"
            return True, "ok"
        if action == "exit":
            if st.position.side != "long":
                return False, "no_position_to_exit"
            return True, "ok"

        return False, f"unknown_action:{action}"
