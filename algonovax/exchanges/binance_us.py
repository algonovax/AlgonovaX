import os, ccxt
from .base import BaseExchange
from algonovax.strategies.types import Side, coerce_side

class BinanceUSExchange(BaseExchange):
    def __init__(self):
        """
        Initialize the Binance US exchange client.
        
        Creates and assigns a ccxt.binanceus client to the instance, configured with the API key and secret taken from the environment variables `BINANCE_API_KEY` and `BINANCE_API_SECRET`, and with rate limiting enabled.
        """
        self.client = ccxt.binanceus({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True
        })

    def execute_trade(self, symbol, side, amount, price=None):
        """
        Execute a market buy or sell order for the given symbol.
        
        Parameters:
            symbol (str): Trading pair symbol (e.g., "BTC/USD").
            side (Side | str): Order side; will be coerced to a Side enum to determine buy or sell.
            amount (float): Quantity to trade.
            price (float | None): Accepted for compatibility but ignored for market orders.
        
        Returns:
            dict: Order object as returned by the exchange client (ccxt).
        """
        if coerce_side(side) == Side.BUY:

            return self.client.create_market_buy_order(symbol, amount)
        else:
            return self.client.create_market_sell_order(symbol, amount)