from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ccxt

from algonovax.utils.net import force_ipv4


@dataclass(frozen=True)
class BinanceUSMarket:
    symbol: str
    timeframe: str
    limit: int = 3

    def snapshot(self) -> dict[str, Any]:
        force_ipv4()
        ex = ccxt.binanceus({"enableRateLimit": True})
        try:
            t = ex.fetch_ticker(self.symbol)
            o = ex.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=self.limit)
        finally:
            try:
                ex.close()
            except Exception:
                pass

        return {
            "exchange": "binanceus",
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "ticker": {
                "bid": t.get("bid"),
                "ask": t.get("ask"),
                "last": t.get("last"),
                "baseVolume": t.get("baseVolume"),
                "quoteVolume": t.get("quoteVolume"),
                "timestamp": t.get("timestamp"),
            },
            "ohlcv_tail": o[-3:] if o else [],
        }
