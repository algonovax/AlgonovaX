import os, ccxt
from .base import BaseExchange
from algonovax.strategies.types import Side, coerce_side

class KrakenExchange(BaseExchange):
    def __init__(self):
        """
        Initialize the exchange wrapper and create a configured ccxt Kraken client.
        
        Creates and assigns a ccxt Kraken client to `self.client` using API credentials read from the environment variables `KRAKEN_API_KEY` and `KRAKEN_API_SECRET`, with built-in rate limiting enabled.
        """
        self.client = ccxt.kraken({
            "apiKey": os.getenv("KRAKEN_API_KEY"),
            "secret": os.getenv("KRAKEN_API_SECRET"),
            "enableRateLimit": True
        })

    def execute_trade(self, symbol, side, amount, price=None):
        """
        Place a market order (buy or sell) for the given symbol based on the provided side.
        
        Parameters:
            symbol (str): Trading pair symbol (e.g., "BTC/USD").
            side (str|Side): Side indicator; interpreted to determine buy versus sell.
            amount (float): Quantity to trade.
            price (float, optional): Ignored for market orders; included for API compatibility.
        
        Returns:
            dict: Order details as returned by the exchange client for the created market order.
        """
        if coerce_side(side) == Side.BUY:

            return self.client.create_market_buy_order(symbol, amount)
        else:
            return self.client.create_market_sell_order(symbol, amount)