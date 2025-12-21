import os, json
from datetime import datetime
from .base import BaseExchange

class PaperExchange(BaseExchange):
    def __init__(self, wallet_path):
        self.wallet_path = os.path.expanduser(wallet_path)
        if not os.path.exists(self.wallet_path):
            raise RuntimeError("Paper wallet not found")
        with open(self.wallet_path, "r") as f:
            self.wallet = json.load(f)

    def execute_trade(self, symbol, side, amount, price):
        amount = float(amount)
        price = float(price)
        if side == "buy":
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
