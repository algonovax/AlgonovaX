from __future__ import annotations

import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    """
    Compute the simple moving average over a fixed-length rolling window.
    
    Parameters:
        s (pd.Series): Input series of values to average.
        n (int): Window length in periods used for the moving average.
    
    Returns:
        pd.Series: Simple moving average of `s` using a window of length `n`. Values for positions with fewer than `n` preceding observations are NaN.
    """
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    """
    Compute the exponential moving average of a pandas Series using the specified span.
    
    Parameters:
        s (pd.Series): Input time series to smooth.
        n (int): Span used for the EMA calculation; also applied as `min_periods`, so the first `n-1` values will be missing.
    
    Returns:
        pd.Series: EMA of `s` computed with `span=n` and `adjust=False`.
    """
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """
    Compute the Relative Strength Index (RSI) for a series of closing prices.
    
    Parameters:
        close (pd.Series): Series of closing prices indexed by time.
        n (int): Look-back period for the RSI calculation (default 14).
    
    Returns:
        pd.Series: RSI values on a 0–100 scale, with initial periods backfilled to produce values for the full index.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()

    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    out = 100 - (100 / (1 + rs))
    return out.bfill()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """
    Compute the Average True Range (ATR) over a lookback period.
    
    Parameters:
        df (pd.DataFrame): DataFrame containing 'high', 'low', and 'close' columns.
        n (int): Lookback period for the ATR calculation (default 14).
    
    Returns:
        pd.Series: ATR values computed from the True Range (maximum of high-low, high-prev_close, low-prev_close) using an exponential smoothing; early entries will be missing until `n` periods are available.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()