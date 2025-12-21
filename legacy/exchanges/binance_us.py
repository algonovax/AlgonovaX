import os, ccxt
from .base import BaseExchange

class BinanceUSExchange(BaseExchange):
    def __init__(self):
        self.client = ccxt.binanceus({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True
        })

    def execute_trade(self, symbol, side, amount, price=None):
        if side == "buy":
            return self.client.create_market_buy_order(symbol, amount)
        else:
            return self.client.create_market_sell_order(symbol, amount)
