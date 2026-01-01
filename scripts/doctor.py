from __future__ import annotations
from pathlib import Path
import sys
import subprocess

FILES = {
"algonovax/strategy/ema_cross_mvp.py": """from __future__ import annotations
from algonovax.strategy.base import Strategy, Intent

def _ema(prev: float | None, x: float, n: int) -> float:
    k = 2.0 / (n + 1.0)
    return x if prev is None else (x * k + prev * (1.0 - k))

class EMACrossMVP(Strategy):
    name = "ema_cross_mvp"

    def __init__(self, fast: int = 12, slow: int = 26, stake_quote: float = 100.0):
        self.fast_n = fast
        self.slow_n = slow
        self.stake_quote = stake_quote
        self.ema_fast: float | None = None
        self.ema_slow: float | None = None
        self.prev_fast: float | None = None
        self.prev_slow: float | None = None

    def on_candle(self, candle, state):
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
""",
}

def write_all() -> None:
    for p, content in FILES.items():
        path = Path(p)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"WROTE {p}")

def compile_all() -> None:
    # compile whole package to catch truncation/syntax errors
    cmd = [sys.executable, "-m", "compileall", "-q", "algonovax"]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(r.returncode)
    print("COMPILE OK")

def main() -> None:
    write_all()
    compile_all()

if __name__ == "__main__":
    main()
