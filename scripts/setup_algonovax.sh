#!/usr/bin/env bash
set -e

BASE_DIR="${ALGONOVAX_ROOT:-$HOME/AlgonovaX}"
echo "[INFO] Setting up AlgonovaX in $BASE_DIR"

# Create base directories
mkdir -p "$BASE_DIR"/{data,logs,strategies,exchanges,utils}

# Create empty __init__.py in packages
touch "$BASE_DIR"/strategies/__init__.py
touch "$BASE_DIR"/exchanges/__init__.py
touch "$BASE_DIR"/utils/__init__.py

# Create paper wallet
PAPER_WALLET="$BASE_DIR/paper_wallet.json"
if [ ! -f "$PAPER_WALLET" ]; then
  cat > "$PAPER_WALLET" <<EOL
{
  "balance": {
    "USD": 10000.0,
    "BTC": 0.01
  },
  "trades": []
}
EOL
  echo "[INFO] Created paper_wallet.json with default balances"
else
  echo "[INFO] paper_wallet.json already exists"
fi

# Create .env template
ENV_FILE="$BASE_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" <<EOL
EXCHANGE=paper
PAPER_TRADING_ENABLED=1
PAPER_WALLET_PATH=./paper_wallet.json

KRAKEN_API_KEY=
KRAKEN_API_SECRET=

BINANCE_API_KEY=
BINANCE_API_SECRET=
LIVE_TRADING_ARMED=0
EOL
  echo "[INFO] Created .env template"
else
  echo "[INFO] .env already exists"
fi

# Create data CSV folder and dummy CSV
DATA_CSV="$BASE_DIR/data/BTC_USD.csv"
if [ ! -f "$DATA_CSV" ]; then
  cat > "$DATA_CSV" <<EOL
close
40000
40100
40250
40300
40450
40500
40400
40300
40200
40100
40050
39950
EOL
  echo "[INFO] Created dummy BTC_USD.csv"
else
  echo "[INFO] BTC_USD.csv already exists"
fi

# Create requirements.txt
REQ_FILE="$BASE_DIR/requirements.txt"
cat > "$REQ_FILE" <<EOL
pandas
ccxt
python-dotenv
EOL
echo "[INFO] Created requirements.txt"

# Create utils/logger.py
cat > "$BASE_DIR/utils/logger.py" <<'EOL'
from datetime import datetime

def log(msg: str):
    ts = datetime.utcnow().isoformat()
    print(f"[{ts}] {msg}")
EOL

# Create utils/data_loader.py
cat > "$BASE_DIR/utils/data_loader.py" <<'EOL'
import pandas as pd
from .logger import log
import os

def load_csv_data(path):
    path = os.path.expanduser(path)
    if os.path.exists(path):
        df = pd.read_csv(path)
        log(f"Loaded data from {path}")
    else:
        log(f"CSV missing: {path}. Using dummy data")
        df = pd.DataFrame({
            "close": [40000, 40100, 40250, 40300, 40450, 40500,
                      40400, 40300, 40200, 40100, 40050, 39950]
        })
    return df
EOL

# Create strategies/ema_rsi.py
cat > "$BASE_DIR/strategies/ema_rsi.py" <<'EOL'
import pandas as pd

def generate_signal(df):
    df = df.copy()
    df["ema_short"] = df["close"].ewm(span=5, adjust=False).mean()
    df["ema_long"] = df["close"].ewm(span=20, adjust=False).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    if df["ema_short"].iloc[-1] > df["ema_long"].iloc[-1] and df["rsi"].iloc[-1] < 70:
        return "buy"
    elif df["ema_short"].iloc[-1] < df["ema_long"].iloc[-1] and df["rsi"].iloc[-1] > 30:
        return "sell"
    else:
        return None
EOL

# Create exchanges/base.py
cat > "$BASE_DIR/exchanges/base.py" <<'EOL'
from abc import ABC, abstractmethod

class BaseExchange(ABC):
    @abstractmethod
    def execute_trade(self, symbol: str, side: str, amount: float, price: float = None):
        pass
EOL

# Create exchanges/paper.py
cat > "$BASE_DIR/exchanges/paper.py" <<'EOL'
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
EOL

# Create exchanges/kraken.py
cat > "$BASE_DIR/exchanges/kraken.py" <<'EOL'
import os, ccxt
from .base import BaseExchange

class KrakenExchange(BaseExchange):
    def __init__(self):
        self.client = ccxt.kraken({
            "apiKey": os.getenv("KRAKEN_API_KEY"),
            "secret": os.getenv("KRAKEN_API_SECRET"),
            "enableRateLimit": True
        })

    def execute_trade(self, symbol, side, amount, price=None):
        if side == "buy":
            return self.client.create_market_buy_order(symbol, amount)
        else:
            return self.client.create_market_sell_order(symbol, amount)
EOL

# Create exchanges/binance_us.py
cat > "$BASE_DIR/exchanges/binance_us.py" <<'EOL'
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
EOL

echo "[INFO] AlgonovaX skeleton setup complete!"
echo "[INFO] Next: pip install -r $REQ_FILE"
