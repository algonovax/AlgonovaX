import os
import ccxt
from .base import BaseExchange
from algonovax.strategies.types import Side, coerce_side


class BinanceUSExchange(BaseExchange):
    def __init__(self):
        self.client = ccxt.binanceus(
            {
                "apiKey": os.getenv("BINANCE_API_KEY"),
                "secret": os.getenv("BINANCE_API_SECRET"),
                "enableRateLimit": True,
            }
        )

    def execute_trade(self, symbol, side, amount, price=None):
        if coerce_side(side) == Side.BUY:
            return self.client.create_market_buy_order(symbol, amount)
        else:
            return self.client.create_market_sell_order(symbol, amount)
