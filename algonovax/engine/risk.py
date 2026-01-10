from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple, Dict


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _norm_action(intent: Any) -> str:
    raw = (
        _get(intent, "action", None)
        or _get(intent, "side", None)
        or _get(intent, "signal", None)
        or _get(intent, "type", None)
    )
    s = str(raw or "hold").strip().lower()
    if "." in s:
        s = s.split(".")[-1]

    if s in ("hold", "noop", "none", ""):
        return "hold"
    if s in ("buy", "long", "open_long", "enter", "enter_long", "open"):
        return "buy"
    if s in ("sell", "close", "exit", "close_long", "take_profit", "stop_loss"):
        return "sell"
    return s


def _stake_quote(intent: Any, cfg: Any) -> float:
    v = _get(intent, "stake_quote", None)
    if v is None:
        v = _get(intent, "usd", None)
    if v is None and cfg is not None:
        v = _get(cfg, "stake_quote", None) or _get(
            _get(cfg, "paper", {}), "stake_quote", None
        )
    try:
        return float(v or 0.0)
    except Exception:
        return 0.0


def _cash_quote(state: Any) -> float:
    v = _get(state, "cash_quote", None) or _get(state, "cash", None)
    try:
        return float(v or 0.0)
    except Exception:
        return 0.0


def _pos_qty(state: Any) -> float:
    v = _get(state, "pos_qty_base", None)
    if v is None:
        pos = _get(state, "position", None) or {}
        v = _get(pos, "qty_base", None) or _get(pos, "qty", None)
    try:
        return float(v or 0.0)
    except Exception:
        return 0.0


@dataclass
class RiskConfig:
    """
    Compatibility config object.

    engine.py may pass different keyword args over time (e.g. max_position_pct).
    Accept all kwargs and store in .extra.
    """

    min_stake_quote: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, min_stake_quote: float = 0.0, **kwargs: Any):
        object.__setattr__(self, "min_stake_quote", float(min_stake_quote or 0.0))
        object.__setattr__(self, "extra", dict(kwargs))


class RiskEngine:
    """
    Backwards-compatible interface expected by algonovax.engine.engine.
    """

    def __init__(self, cfg: RiskConfig | None = None):
        self.cfg = cfg or RiskConfig()

    # --- methods engine.py may call (aliases) ---

    def validate_intent(
        self, intent: Any, state: Any, cfg: Any = None
    ) -> Tuple[bool, str]:
        # engine expects this name
        return check_risk(intent=intent, state=state, cfg=cfg, risk_cfg=self.cfg)

    def check(self, intent: Any, state: Any, cfg: Any = None) -> Tuple[bool, str]:
        return self.validate_intent(intent=intent, state=state, cfg=cfg)

    def evaluate(self, intent: Any, state: Any, cfg: Any = None) -> Tuple[bool, str]:
        return self.validate_intent(intent=intent, state=state, cfg=cfg)


def check_risk(
    intent: Any, state: Any, cfg: Any = None, risk_cfg: RiskConfig | None = None
) -> Tuple[bool, str]:
    try:
        action = _norm_action(intent)

        if action == "hold":
            return True, "ok"

        if action == "buy":
            stake = _stake_quote(intent, cfg)
            cash = _cash_quote(state)

            # If stake not provided, allow (engine may size later)
            if stake <= 0:
                return True, "ok"

            floor = 0.0
            try:
                if risk_cfg is not None:
                    floor = float(getattr(risk_cfg, "min_stake_quote", 0.0) or 0.0)
            except Exception:
                floor = 0.0
            if floor > 0 and stake < floor:
                return False, f"stake_too_small:{stake:.2f}<min:{floor:.2f}"

            if cash + 1e-9 < stake:
                return False, f"insufficient_cash:{cash:.2f}<stake:{stake:.2f}"
            return True, "ok"

        if action == "sell":
            qty = _pos_qty(state)
            if qty <= 0:
                return False, "no_position"
            return True, "ok"

        return False, f"unknown_action:{action}"

    except Exception as e:
        return False, f"risk_error:{type(e).__name__}:{e}"
