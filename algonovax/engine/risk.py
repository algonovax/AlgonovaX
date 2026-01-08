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
        """
        Initialize the RiskEngine with a risk configuration.
        
        Parameters:
            cfg (RiskConfig): Configuration containing `max_position_pct`, `max_risk_pct`, and `max_daily_drawdown_pct`.
        """
        self.cfg = cfg

    def validate_intent(self, intent: Any, st: Any) -> Tuple[bool, str]:
        """
        Validate a trading intent against the current state and the engine's risk limits.
        
        The validator permits a "hold" intent, enforces a daily drawdown limit (blocks if the relative drawdown from `st.day_start_equity` to `st.equity` is greater than or equal to `self.cfg.max_daily_drawdown_pct`), allows "enter" only when `st.position.side` is "flat", allows "exit" only when `st.position.side` is "long", and rejects any unrecognized action.
        
        Parameters:
        	intent (Any): Object with an `action` attribute expected to be one of "hold", "enter", or "exit".
        	st (Any): Execution state object exposing `day_start_equity`, `equity`, and `position.side`.
        
        Returns:
        	tuple: `True` and "ok" if the intent is allowed; otherwise `False` and a short reason string (e.g., "daily_drawdown_block ...", "already_in_position", "no_position_to_exit", or "unknown_action:<action>").
        """
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