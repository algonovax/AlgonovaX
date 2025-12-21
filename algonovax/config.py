from __future__ import annotations

import os
from dataclasses import dataclass

def _getenv(key: str, default: str | None = None) -> str | None:
    v = os.getenv(key)
    return v if v not in (None, "") else default

def _getbool(key: str, default: bool = False) -> bool:
    v = _getenv(key)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}

def _getint(key: str, default: int) -> int:
    v = _getenv(key)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError as e:
        raise ValueError(f"{key} must be an int") from e

def _getfloat(key: str, default: float) -> float:
    v = _getenv(key)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError as e:
        raise ValueError(f"{key} must be a float") from e

@dataclass(frozen=True)
class Settings:
    env: str
    paper_trading: bool
    live_trading: bool

    exchange: str
    symbol: str
    timeframe: str

    host: str
    port: int

    log_level: str
    kill_switch_path: str

    max_daily_loss_usd: float
    max_open_positions: int

    kraken_api_key: str | None
    kraken_api_secret: str | None

def load_settings() -> Settings:
    env = _getenv("ENV", "dev")
    paper_trading = _getbool("PAPER_TRADING_ENABLED", True)

    # Live trading is explicit, never default-on.
    live_trading = _getbool("LIVE_TRADING_ENABLED", False)

    exchange = _getenv("EXCHANGE", "paper")
    symbol = _getenv("SYMBOL", "BTC/USD")
    timeframe = _getenv("TIMEFRAME", "1m")

    host = _getenv("HOST", "127.0.0.1")
    port = _getint("PORT", 8001)

    log_level = _getenv("LOG_LEVEL", "INFO")
    kill_switch_path = _getenv("KILL_SWITCH_PATH", "./data/KILL_SWITCH") or "./data/KILL_SWITCH"

    max_daily_loss_usd = _getfloat("MAX_DAILY_LOSS_USD", 50.0)
    max_open_positions = _getint("MAX_OPEN_POSITIONS", 1)

    kraken_api_key = _getenv("KRAKEN_API_KEY")
    kraken_api_secret = _getenv("KRAKEN_API_SECRET")

    if live_trading and exchange != "kraken":
        raise RuntimeError("LIVE_TRADING_ENABLED=1 requires EXCHANGE=kraken")

    if exchange == "paper" and not paper_trading:
        raise RuntimeError("EXCHANGE=paper requires PAPER_TRADING_ENABLED=1")

    if exchange == "kraken" and live_trading:
        if not kraken_api_key or not kraken_api_secret:
            raise RuntimeError("Live Kraken trading requires KRAKEN_API_KEY and KRAKEN_API_SECRET")

    return Settings(
        env=env,
        paper_trading=paper_trading,
        live_trading=live_trading,
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        host=host,
        port=port,
        log_level=log_level,
        kill_switch_path=kill_switch_path,
        max_daily_loss_usd=max_daily_loss_usd,
        max_open_positions=max_open_positions,
        kraken_api_key=kraken_api_key,
        kraken_api_secret=kraken_api_secret,
    )
