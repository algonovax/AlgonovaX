from __future__ import annotations
import json
import time
import traceback
from pathlib import Path
from typing import Any, Iterable


# SAFE_INTENT_ATTR_HELPER
def _safe_attr(obj: object, name: str, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


# TB_ON_ALL_FATAL
def _tb() -> str:
    try:
        return traceback.format_exc()
    except Exception:
        return ""


from algonovax.engine.risk import RiskEngine, RiskConfig
from algonovax.engine.state import EngineState, load_state, save_state
from algonovax.engine.paper import apply_slippage, compute_fee
from algonovax.data.feeds import dummy_candle_feed
from algonovax.data.kraken_ohlc import kraken_ohlc_feed

KILL_SWITCH_PATH = Path("data/KILL_SWITCH")
STATE_PATH = "data/state.json"


def log_event(event: dict[str, Any]) -> None:
    Path("algonovax/logs").mkdir(parents=True, exist_ok=True)
    print(json.dumps(event, separators=(",", ":"), ensure_ascii=False), flush=True)


def _select_feed(cfg: dict[str, Any]) -> Iterable[dict]:
    mode = str(cfg.get("mode", "paper")).lower()
    pair = str(cfg.get("pair"))
    if mode in {"paper", "live"}:
        interval_min = int(cfg.get("data", {}).get("interval_min", 5))
        poll_seconds = int(cfg.get("data", {}).get("poll_seconds", 10))
        return kraken_ohlc_feed(
            pair, interval_min=interval_min, poll_seconds=poll_seconds
        )
    return dummy_candle_feed(pair)


def _mark_to_market(st: EngineState, last_price: float) -> None:
    st.last_price = last_price
    if st.position.side == "long" and st.position.qty_base > 0:
        st.unrealized_pnl = (
            last_price - st.position.entry_price
        ) * st.position.qty_base
    else:
        st.unrealized_pnl = 0.0
    st.equity = st.cash_quote + (
        st.position.qty_base * last_price if st.position.side == "long" else 0.0
    )


def _enter_long(
    st: EngineState,
    price: float,
    stake_quote: float,
    fee_rate: float,
    slippage_rate: float,
    ts: int,
) -> dict[str, Any]:
    exec_price = apply_slippage(price, "buy", slippage_rate)
    stake = min(max(0.0, stake_quote), st.cash_quote)
    qty = 0.0 if exec_price <= 0 else (stake / exec_price)
    notional = qty * exec_price
    fee = compute_fee(notional, fee_rate)
    total = notional + fee
    if total > st.cash_quote or qty <= 0:
        return {
            "ok": False,
            "reason": "insufficient_cash_or_qty",
            "exec_price": exec_price,
            "stake": stake,
        }

    st.cash_quote -= total
    st.position.side = "long"
    st.position.qty_base = qty
    st.position.entry_price = exec_price
    _mark_to_market(st, exec_price)
    return {
        "ok": True,
        "side": "buy",
        "price": exec_price,
        "qty_base": qty,
        "fee_quote": fee,
        "ts": ts,
    }


def _exit_long(
    st: EngineState, price: float, fee_rate: float, slippage_rate: float, ts: int
) -> dict[str, Any]:
    if st.position.side != "long" or st.position.qty_base <= 0:
        return {"ok": False, "reason": "no_position"}

    exec_price = apply_slippage(price, "sell", slippage_rate)
    qty = st.position.qty_base
    notional = qty * exec_price
    fee = compute_fee(notional, fee_rate)
    proceeds = notional - fee

    pnl = (exec_price - st.position.entry_price) * qty - fee
    st.cash_quote += proceeds
    st.realized_pnl += pnl
    st.position.side = "flat"
    st.position.qty_base = 0.0
    st.position.entry_price = 0.0
    _mark_to_market(st, exec_price)
    return {
        "ok": True,
        "side": "sell",
        "price": exec_price,
        "qty_base": qty,
        "fee_quote": fee,
        "pnl": pnl,
        "ts": ts,
    }


def run(cfg: dict[str, Any], strategy) -> int:
    risk_cfg = cfg.get("risk", {})
    risk = RiskEngine(
        RiskConfig(
            max_position_pct=float(risk_cfg.get("max_position_pct", 0.10)),
            max_risk_pct=float(risk_cfg.get("max_risk_pct", 0.01)),
            max_daily_drawdown_pct=float(risk_cfg.get("max_daily_drawdown_pct", 0.05)),
        )
    )

    mode = str(cfg.get("mode", "paper")).lower()
    pair = str(cfg.get("pair"))
    cash0 = float(cfg.get("paper", {}).get("starting_cash_quote", 1000.0))
    st = load_state(
        STATE_PATH,
        EngineState(
            mode=mode, pair=pair, cash_quote=cash0, equity=cash0, day_start_equity=cash0
        ),
    )

    fee_rate = float(cfg.get("costs", {}).get("fee_rate", 0.001))
    slippage_rate = float(cfg.get("costs", {}).get("slippage_rate", 0.0005))
    default_stake = float(cfg.get("paper", {}).get("stake_quote", 100.0))

    strategy.on_start(st.to_dict())
    log_event(
        {
            "type": "START",
            "strategy": getattr(strategy, "name", "unknown"),
            "state": st.to_dict(),
        }
    )

    try:
        feed = _select_feed(cfg)
        for candle in feed:
            if KILL_SWITCH_PATH.exists():
                log_event({"type": "KILL_SWITCH", "path": str(KILL_SWITCH_PATH)})
                break

            if "error" in candle:
                log_event({"type": "DATA_ERROR", "data": candle})
                continue

            last_price = float(candle["close"])
            _mark_to_market(st, last_price)

            # ACTION_NORMALIZE_BUY_SELL__AND__STAKE_DEFAULT_ON_ZERO
            # TB_ON_STRATEGY_EXCEPTION
            try:
                intent = strategy.on_candle(candle, st.to_dict())
            except Exception as e:
                # DEBUG_TB_RERAISE_FATAL
                tb = traceback.format_exc()
                # TB_ON_ANY_FATAL_EXCEPTION
                log_event(
                    {
                        "type": "FATAL",
                        "where": "strategy.on_candle",
                        "exc": repr(e),
                        "tb": traceback.format_exc(),
                    }
                )
                raise

            ok, reason = risk.validate_intent(intent, st, cfg)

            # Normalize action semantics across strategies:
            #   buy/long/open -> enter
            #   sell/close/exit -> exit
            raw_action = (
                _safe_attr(intent, "side", None)
                or _safe_attr(intent, "action", None)
                or "hold"
            )
            act = str(raw_action).strip().lower()
            if "." in act:
                act = act.split(".")[-1]
            if act in ("buy", "long", "open", "open_long", "enter", "enter_long"):
                act = "enter"
            elif act in ("sell", "close", "close_long", "exit", "exit_long"):
                act = "exit"
            else:
                act = "hold"

                # FORCE_ENTER_ONCE_TICK_27
                # Force a single ENTER on tick 27 to validate fill pipeline.
            fill = None
            if ok and mode == "paper":
                if act == "enter":
                    # stake_quote <= 0 means 'use default_stake'
                    sr = getattr(intent, "stake_quote", None)
                    try:
                        sv = float(sr) if sr is not None else 0.0
                    except Exception:
                        sv = 0.0
                    stake = default_stake if sv <= 0.0 else sv
                    fill = _enter_long(
                        st,
                        last_price,
                        stake,
                        fee_rate,
                        slippage_rate,
                        int(candle["ts"]),
                    )
                elif act == "exit":
                    fill = _exit_long(
                        st, last_price, fee_rate, slippage_rate, int(candle["ts"])
                    )
            save_state(STATE_PATH, st)

            log_event(
                {
                    "type": "TICK",
                    "candle": candle,
                    "intent": {
                        "action": act,
                        "side": str(_safe_attr(intent, "side", "hold")),
                        "reason": str(_safe_attr(intent, "reason", "")),
                        "stake_quote": float(_safe_attr(intent, "stake_quote", 0) or 0),
                    },
                    "risk": {"ok": ok, "reason": reason},
                    "fill": fill,
                    "state": {
                        "cash_quote": st.cash_quote,
                        "pos_side": st.position.side,
                        "pos_qty_base": st.position.qty_base,
                        "pos_entry": st.position.entry_price,
                        "realized_pnl": st.realized_pnl,
                        "unrealized_pnl": st.unrealized_pnl,
                        "equity": st.equity,
                    },
                }
            )

            # TERMUX_FAST_ENGINE_SLEEP

            try:
                _ps = float(cfg.get("engine", {}).get("poll_seconds", 1))

            except Exception:
                _ps = 1.0

            import os as _os

            time.sleep(0.05 if _os.environ.get("ALGONOVAX_TERMUX_FAST") == "1" else _ps)

    except KeyboardInterrupt:
        log_event({"type": "STOP", "reason": "keyboard_interrupt"})
    except Exception as e:
        log_event({"type": "FATAL", "error": str(e), "exc": repr(e), "tb": _tb()})
        return 1
    finally:
        try:
            strategy.on_stop(st.to_dict())
        except Exception as e:
            log_event({"type": "WARN", "error": f"on_stop failed: {e}"})

    log_event({"type": "EXIT"})
    return 0
