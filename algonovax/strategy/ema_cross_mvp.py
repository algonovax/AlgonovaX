from __future__ import annotations
from algonovax.strategy.base import Strategy, Intent

def _ema(prev: float | None, x: float, n: int) -> float:
    """
    Compute the updated exponential moving average (EMA) given a new sample.
    
    If `prev` is None, the function initializes the EMA to the current sample `x`. Otherwise it returns the EMA updated using smoothing factor k = 2 / (n + 1).
    
    Parameters:
        prev (float | None): Previous EMA value, or `None` to initialize.
        x (float): Current sample value (e.g., latest price).
        n (int): EMA period used to compute the smoothing factor.
    
    Returns:
        float: The updated EMA value.
    """
    k = 2.0 / (n + 1.0)
    return x if prev is None else (x * k + prev * (1.0 - k))

class EMACrossMVP(Strategy):
    name = "ema_cross_mvp"

    def __init__(self, fast: int = 12, slow: int = 26, stake_quote: float = 100.0):
        """
        Initialize the EMA crossover strategy with periods and entry stake, and set internal EMA state to uninitialized.
        
        Parameters:
            fast (int): Period for the fast EMA (default 12).
            slow (int): Period for the slow EMA (default 26).
            stake_quote (float): Quote-currency amount to stake when entering a trade (default 100.0).
        
        Description:
            Sets strategy parameters (`fast_n`, `slow_n`, `stake_quote`) and initializes EMA tracking fields
            (`ema_fast`, `ema_slow`, `prev_fast`, `prev_slow`) to None to indicate warmup/uninitialized state.
        """
        self.fast_n = fast
        self.slow_n = slow
        self.stake_quote = stake_quote
        self.ema_fast: float | None = None
        self.ema_slow: float | None = None
        self.prev_fast: float | None = None
        self.prev_slow: float | None = None

    def on_candle(self, candle, state):
        """
        Process a new market candle, update fast and slow EMAs, and produce a trading Intent when an EMA crossover signal occurs.
        
        Parameters:
            candle (Mapping): Market candle containing a "close" field (numeric), used to update EMAs.
            state (dict): Strategy state; may contain "position" -> {"side": str} where side is typically "flat" or "long".
        
        Returns:
            Intent: 
                - `Intent(action="enter", side="buy", reason="ema_cross_up", stake_quote=...)` when the fast EMA crosses above the slow EMA and current position is "flat".
                - `Intent(action="exit", side="sell", reason="ema_cross_down")` when the fast EMA crosses below the slow EMA and current position is "long".
                - `Intent(action="hold", reason="warmup")` while EMAs are being initialized.
                - `Intent(action="hold", reason="no_signal")` when no trade signal is present.
        """
        close = float(candle["close"])
        self.prev_fast, self.prev_slow = self.ema_fast, self.ema_slow
        self.ema_fast = _ema(self.ema_fast, close, self.fast_n)
        self.ema_slow = _ema(self.ema_slow, close, self.slow_n)

        if self.prev_fast is None or self.prev_slow is None:
            return Intent(action="hold", reason="warmup")

        crossed_up = (self.prev_fast <= self.prev_slow) and (self.ema_fast > self.ema_slow)
        crossed_dn = (self.prev_fast >= self.prev_slow) and (self.ema_fast < self.ema_slow)

        pos_side = (state.get("position") or {}).get("side", "flat")

        if crossed_up and pos_side == "flat":
            return Intent(action="enter", side="buy", reason="ema_cross_up", stake_quote=self.stake_quote)

        if crossed_dn and pos_side == "long":
            return Intent(action="exit", side="sell", reason="ema_cross_down")

        return Intent(action="hold", reason="no_signal")