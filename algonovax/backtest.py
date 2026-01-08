from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

Signal = Literal["BUY", "SELL", "HOLD"]

@dataclass(frozen=True)
class Candle:
    ts: int
    o: float
    h: float
    l: float
    c: float
    v: float

def load_kraken_ohlcv_json(path: Path) -> list[Candle]:
    """
    Load OHLCV candles from a Kraken-style JSON file accepting either list-of-arrays or list-of-dicts formats.
    
    Parameters:
        path (Path): Path to a UTF-8 encoded JSON file. Each top-level item must be either:
            - a list/array with at least six elements [ts, open, high, low, close, volume, ...], or
            - a mapping containing timestamp under "ts", "timestamp", or "time" and price/volume under "open", "high", "low", "close", "volume".
    
    Returns:
        list[Candle]: Parsed and validated Candle objects sorted by timestamp in ascending order.
    
    Raises:
        RuntimeError: If the file cannot be read, parsed, contains no valid candles, or any other error occurs while loading.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Expected list")

        out: list[Candle] = []
        for row in raw:
            if isinstance(row, list) and len(row) >= 6:
                ts, o, h, l, c, v = row[:6]
            elif isinstance(row, dict):
                ts = row.get("ts") or row.get("timestamp") or row.get("time")
                o = row.get("open"); h = row.get("high"); l = row.get("low"); c = row.get("close"); v = row.get("volume")
            else:
                continue
            out.append(Candle(int(ts), float(o), float(h), float(l), float(c), float(v)))

        if not out:
            raise ValueError("No candles loaded")

        out.sort(key=lambda x: x.ts)
        return out
    except Exception as e:
        raise RuntimeError(f"Failed to load candles from {path}: {e}") from e

@dataclass
class BacktestResult:
    symbol: str
    timeframe: str
    start_ts: int
    end_ts: int
    trades: int
    wins: int
    losses: int
    net_pnl_quote: float
    max_drawdown_quote: float

def to_jsonable(res: BacktestResult) -> dict[str, Any]:
    """
    Convert a BacktestResult into a JSON-serializable dictionary.
    
    Returns:
        dict: A mapping with keys:
            - "symbol": symbol of the instrument (str)
            - "timeframe": timeframe identifier (str)
            - "start_ts": start timestamp of the backtest (int)
            - "end_ts": end timestamp of the backtest (int)
            - "trades": total number of trades executed (int)
            - "wins": number of winning trades (int)
            - "losses": number of losing trades (int)
            - "net_pnl_quote": net profit and loss in quote currency (float)
            - "max_drawdown_quote": maximum drawdown in quote currency (float)
    """
    return {
        "symbol": res.symbol,
        "timeframe": res.timeframe,
        "start_ts": res.start_ts,
        "end_ts": res.end_ts,
        "trades": res.trades,
        "wins": res.wins,
        "losses": res.losses,
        "net_pnl_quote": res.net_pnl_quote,
        "max_drawdown_quote": res.max_drawdown_quote,
    }

@dataclass
class Trade:
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float
    gross_pnl_quote: float
    fee_quote: float
    net_pnl_quote: float
    reason: str

StrategyFn = Callable[[list[float], list[float], list[float]], Signal]
ATRFn = Callable[[list[float], list[float], list[float]], float]

def run_backtest_atr_exits(
    candles: list[Candle],
    symbol: str,
    timeframe: str,
    strategy: StrategyFn,
    atr_value: ATRFn,
    fee_rate: float = 0.002,       # per side
    slippage_rate: float = 0.0005, # per side
    stake_quote: float = 100.0,
    stop_atr_mult: float = 2.0,
    tp_atr_mult: float = 3.0,
    min_hold_bars: int = 6,
    cooldown_bars: int = 6,
) -> tuple[BacktestResult, list[Trade]]:
    """
    Run an ATR-based backtest that entries on a strategy signal and exits by ATR stop, take-profit, or sell signal.
    
    Parameters:
        candles (list[Candle]): Sequential candlesticks to backtest.
        symbol (str): Asset symbol recorded in the result.
        timeframe (str): Timeframe label recorded in the result.
        strategy (StrategyFn): Signal function returning "BUY", "SELL", or "HOLD".
        atr_value (ATRFn): Function that computes ATR from highs, lows, closes.
        fee_rate (float): Per-side fee rate applied to stake at entry and exit.
        slippage_rate (float): Per-side slippage applied to entry and exit prices.
        stake_quote (float): Quote currency stake sized per trade.
        stop_atr_mult (float): ATR multiplier used to compute the stop-loss below entry.
        tp_atr_mult (float): ATR multiplier used to compute the take-profit above entry.
        min_hold_bars (int): Minimum number of bars to hold a position before allowing signal exits.
        cooldown_bars (int): Bars to wait after an exit before allowing a new entry.
    
    Returns:
        tuple[BacktestResult, list[Trade]]: A BacktestResult summarizing performance and a ledger of Trade records.
    """
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []

    in_pos = False
    entry_price = 0.0
    entry_ts = 0
    bars_in_pos = 0
    cooldown = 0

    pnl = 0.0
    peak = 0.0
    max_dd = 0.0

    trades = wins = losses = 0
    ledger: list[Trade] = []

    for c in candles:
        highs.append(c.h); lows.append(c.l); closes.append(c.c)

        if cooldown > 0:
            cooldown -= 1

        if in_pos:
            bars_in_pos += 1

            try:
                a = float(atr_value(highs, lows, closes))
            except Exception:
                a = 0.0

            stop_price = entry_price - stop_atr_mult * a if a > 0 else None
            tp_price = entry_price + tp_atr_mult * a if a > 0 else None

            exit_reason: str | None = None
            if stop_price is not None and c.c <= stop_price:
                exit_reason = "STOP"
            elif tp_price is not None and c.c >= tp_price:
                exit_reason = "TAKE_PROFIT"
            else:
                sig = strategy(highs, lows, closes)
                if sig == "SELL" and bars_in_pos >= min_hold_bars:
                    exit_reason = "SIGNAL"

            if exit_reason:
                exit_price = c.c * (1.0 - slippage_rate)
                ret = (exit_price - entry_price) / entry_price
                gross = stake_quote * ret

                fee_total = stake_quote * fee_rate * 2.0
                # entry fee was subtracted at entry; subtract exit fee now
                pnl += gross - (stake_quote * fee_rate)
                net = gross - fee_total

                ledger.append(Trade(
                    entry_ts=entry_ts,
                    exit_ts=c.ts,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    gross_pnl_quote=round(gross, 6),
                    fee_quote=round(fee_total, 6),
                    net_pnl_quote=round(net, 6),
                    reason=exit_reason,
                ))

                trades += 1
                if net >= 0:
                    wins += 1
                else:
                    losses += 1

                in_pos = False
                entry_price = 0.0
                entry_ts = 0
                bars_in_pos = 0
                cooldown = cooldown_bars

        if (not in_pos) and cooldown == 0:
            sig = strategy(highs, lows, closes)
            if sig == "BUY":
                entry_ts = c.ts
                entry_price = c.c * (1.0 + slippage_rate)
                pnl -= stake_quote * fee_rate
                in_pos = True
                bars_in_pos = 0

        if pnl > peak:
            peak = pnl
        dd = peak - pnl
        if dd > max_dd:
            max_dd = dd

    res = BacktestResult(
        symbol=symbol,
        timeframe=timeframe,
        start_ts=candles[0].ts,
        end_ts=candles[-1].ts,
        trades=trades,
        wins=wins,
        losses=losses,
        net_pnl_quote=round(pnl, 6),
        max_drawdown_quote=round(max_dd, 6),
    )
    return res, ledger