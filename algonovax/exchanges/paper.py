import os, json
from datetime import datetime
from .base import BaseExchange
from algonovax.strategies.types import Side, coerce_side

class PaperExchange(BaseExchange):
    def __init__(self, wallet_path):
        """
        Initialize the PaperExchange and load wallet data from a JSON file.
        
        Parameters:
        	wallet_path (str): Filesystem path to the wallet JSON file; user (~) expansion is applied. Raises RuntimeError("Paper wallet not found") if the file does not exist.
        
        Side effects:
        	Sets `self.wallet_path` to the expanded path and `self.wallet` to the parsed JSON contents.
        """
        self.wallet_path = os.path.expanduser(wallet_path)
        if not os.path.exists(self.wallet_path):
            raise RuntimeError("Paper wallet not found")
        with open(self.wallet_path, "r") as f:
            self.wallet = json.load(f)

    def execute_trade(self, symbol, side, amount, price):
        """
        Execute a paper trade and persist the updated wallet.
        
        Executes a buy or sell for the given symbol, updates USD and BTC balances accordingly, appends the trade (including a UTC ISO 8601 timestamp) to the wallet's "trades" list, and writes the wallet JSON back to disk.
        
        Parameters:
            symbol (str): Trading pair symbol (e.g., "BTC/USD").
            side (str | Side): Trade side; interpreted as buy or sell.
            amount (float | int): Quantity of base asset to trade.
            price (float | int): Price per unit of base asset in quote currency.
        
        Raises:
            RuntimeError: If USD balance is insufficient for a buy or BTC balance is insufficient for a sell.
        """
        amount = float(amount)
        price = float(price)
        if coerce_side(side) == Side.BUY:

            cost = amount * price
            if self.wallet["balance"]["USD"] < cost:
                raise RuntimeError("Insufficient USD balance")
            self.wallet["balance"]["USD"] -= cost
            self.wallet["balance"]["BTC"] += amount
        else:
            if self.wallet["balance"]["BTC"] < amount:
                raise RuntimeError("Insufficient BTC balance")
            self.wallet["balance"]["BTC"] -= amount
            self.wallet["balance"]["USD"] += amount * price

        self.wallet.setdefault("trades", []).append({
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "timestamp": datetime.utcnow().isoformat()
        })

        with open(self.wallet_path, "w") as f:
            json.dump(self.wallet, f, indent=2)