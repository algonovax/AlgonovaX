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
