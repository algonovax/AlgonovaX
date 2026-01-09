from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Iterable

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
        return kraken_ohlc_feed(pair, interval_min=interval_min, poll_seconds=poll_seconds)
    return dummy_candle_feed(pair)

def _mark_to_market(st: EngineState, last_price: float) -> None:
    st.last_price = last_price
    if st.position.side == "long" and st.position.qty_base > 0:
        st.unrealized_pnl = (last_price - st.position.entry_price) * st.position.qty_base
    else:
        st.unrealized_pnl = 0.0
    st.equity = st.cash_quote + (st.position.qty_base * last_price if st.position.side == "long" else 0.0)

def _enter_long(st: EngineState, price: float, stake_quote: float, fee_rate: float, slippage_rate: float, ts: int) -> dict[str, Any]:
    exec_price = apply_slippage(price, "buy", slippage_rate)
    stake = min(max(0.0, stake_quote), st.cash_quote)
    qty = 0.0 if exec_price <= 0 else (stake / exec_price)
    notional = qty * exec_price
    fee = compute_fee(notional, fee_rate)
    total = notional + fee
    if total > st.cash_quote or qty <= 0:
        return {"ok": False, "reason": "insufficient_cash_or_qty", "exec_price": exec_price, "stake": stake}

    st.cash_quote -= total
    st.position.side = "long"
    st.position.qty_base = qty
    st.position.entry_price = exec_price
    _mark_to_market(st, exec_price)
    return {"ok": True, "side": "buy", "price": exec_price, "qty_base": qty, "fee_quote": fee, "ts": ts}

def _exit_long(st: EngineState, price: float, fee_rate: float, slippage_rate: float, ts: int) -> dict[str, Any]:
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
    return {"ok": True, "side": "sell", "price": exec_price, "qty_base": qty, "fee_quote": fee, "pnl": pnl, "ts": ts}

def run(cfg: dict[str, Any], strategy) -> int:
    risk_cfg = cfg.get("risk", {})
    risk = RiskEngine(RiskConfig(
        max_position_pct=float(risk_cfg.get("max_position_pct", 0.10)),
        max_risk_pct=float(risk_cfg.get("max_risk_pct", 0.01)),
        max_daily_drawdown_pct=float(risk_cfg.get("max_daily_drawdown_pct", 0.05)),
    ))

    mode = str(cfg.get("mode", "paper")).lower()
    pair = str(cfg.get("pair"))
    cash0 = float(cfg.get("paper", {}).get("starting_cash_quote", 1000.0))
    st = load_state(STATE_PATH, EngineState(mode=mode, pair=pair, cash_quote=cash0, equity=cash0, day_start_equity=cash0))

    fee_rate = float(cfg.get("costs", {}).get("fee_rate", 0.001))
    slippage_rate = float(cfg.get("costs", {}).get("slippage_rate", 0.0005))
    default_stake = float(cfg.get("paper", {}).get("stake_quote", 100.0))

    strategy.on_start(st.to_dict())
    log_event({"type":"START","strategy":getattr(strategy,"name","unknown"),"state":st.to_dict()})

    try:
        feed = _select_feed(cfg)
        for candle in feed:
            if KILL_SWITCH_PATH.exists():
                log_event({"type":"KILL_SWITCH","path":str(KILL_SWITCH_PATH)})
                break

            if "error" in candle:
                log_event({"type":"DATA_ERROR","data":candle})
                continue

            last_price = float(candle["close"])
            _mark_to_market(st, last_price)

            intent = strategy.on_candle(candle, st.to_dict())
            ok, reason = risk.validate_intent(intent, st)

            fill = None
            if ok and mode == "paper":
                if intent.action == "enter":
                    stake = float(intent.stake_quote) if intent.stake_quote is not None else default_stake
                    fill = _enter_long(st, last_price, stake, fee_rate, slippage_rate, int(candle["ts"]))
                elif intent.action == "exit":
                    fill = _exit_long(st, last_price, fee_rate, slippage_rate, int(candle["ts"]))

            save_state(STATE_PATH, st)

            log_event({
                "type":"TICK",
                "candle":candle,
                "intent":{"action":intent.action,"side":intent.side,"reason":intent.reason,"stake_quote":intent.stake_quote},
                "risk":{"ok":ok,"reason":reason},
                "fill":fill,
                "state":{
                    "cash_quote":st.cash_quote,
                    "pos_side":st.position.side,
                    "pos_qty_base":st.position.qty_base,
                    "pos_entry":st.position.entry_price,
                    "realized_pnl":st.realized_pnl,
                    "unrealized_pnl":st.unrealized_pnl,
                    "equity":st.equity,
                }
            })

            time.sleep(float(cfg.get("engine", {}).get("poll_seconds", 1)))
    except KeyboardInterrupt:
        log_event({"type":"STOP","reason":"keyboard_interrupt"})
    except Exception as e:
        log_event({"type":"FATAL","error":str(e),"exc":repr(e)})
        return 1
    finally:
        try:
            strategy.on_stop(st.to_dict())
        except Exception as e:
            log_event({"type":"WARN","error":f"on_stop failed: {e}"})

    log_event({"type":"EXIT"})
    return 0
