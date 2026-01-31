from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from algonovax.config import Settings
from algonovax.events import OrderFilled

log = logging.getLogger(__name__)

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}


def _write_json_atomic(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


@dataclass
class _Wallet:
    quote: float
    base: float


class PaperExchange:
    """
    Minimal paper exchange:
      - wallet: paper_wallet.json
      - market orders: immediate fill at price_hint (engine must provide)
      - fee: max(PAPER_FEE_QUOTE, notional * PAPER_FEE_RATE)
      - wallet updates are guarded by an OS-level file lock to prevent concurrent writers
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        root = os.environ.get("ALGONOVAX_ROOT") or os.path.expanduser("~/AlgonovaX")
        self.root = Path(root)

        self.wallet_path = Path(os.environ.get("PAPER_WALLET_PATH") or str(self.root / "paper_wallet.json"))
        self.lock_path = self.wallet_path.with_suffix(self.wallet_path.suffix + ".lock")

        self.fee_quote = float(os.environ.get("PAPER_FEE_QUOTE", "0.01"))
        self.fee_rate = float(os.environ.get("PAPER_FEE_RATE", "0.0"))  # 0.001 = 0.1%

        self.default_quote = float(os.environ.get("PAPER_STARTING_CASH_QUOTE", "1000.0"))
        self.default_base = float(os.environ.get("PAPER_STARTING_BASE", "0.0"))

    def _load_wallet_unlocked(self) -> _Wallet:
        j = _read_json(self.wallet_path)
        return _Wallet(
            quote=float(j.get("quote", self.default_quote)),
            base=float(j.get("base", self.default_base)),
        )

    def _save_wallet_unlocked(self, w: _Wallet) -> None:
        _write_json_atomic(self.wallet_path, {"quote": w.quote, "base": w.base})

    def _with_wallet_lock(self):
        # Returns a context manager-like tuple: (fh, locked_bool)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.lock_path, "a+", encoding="utf-8")
        locked = False
        try:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                locked = True
        except Exception:
            # If lock fails, proceed (best-effort) but you should expect races.
            locked = False
        return fh, locked

    def get_last_price(self, symbol: str) -> float:
        v = os.environ.get("PAPER_LAST_PRICE")
        if v:
            try:
                return float(v)
            except Exception:
                pass
        return float(os.environ.get("PAPER_DEFAULT_PRICE", "50000.0"))

    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price_hint: Optional[float] = None,
    ) -> OrderFilled:
        if qty <= 0:
            raise ValueError("qty must be > 0")

        side_n = side.strip().lower()
        if side_n not in ("buy", "sell"):
            raise ValueError("side must be buy/sell")

        if price_hint is None:
            raise RuntimeError("price_hint is required (engine must provide deterministic price)")

        px = float(price_hint)
        cost = qty * px
        fee = max(float(self.fee_quote), float(cost) * float(self.fee_rate))

        fh, _locked = self._with_wallet_lock()
        try:
            w = self._load_wallet_unlocked()
            if os.environ.get("PAPER_DEBUG") == "1":
                log.info(f"paper_wallet_before side={side_n} qty={qty} px={px} quote={w.quote:.8f} base={w.base:.8f}")

            if side_n == "buy":
                need = cost + fee
                if w.quote < need:
                    raise RuntimeError(f"paper insufficient quote: have={w.quote:.6f} need={need:.6f}")
                w.quote -= need
                w.base += qty
            else:
                if w.base < qty:
                    raise RuntimeError(f"paper insufficient base: have={w.base:.6f} need={qty:.6f}")
                w.base -= qty
                w.quote += (cost - fee)
            if os.environ.get("PAPER_DEBUG") == "1":
                log.info(f"paper_wallet_after  side={side_n} qty={qty} px={px} fee={fee:.8f} quote={w.quote:.8f} base={w.base:.8f}")
            self._save_wallet_unlocked(w)

        finally:
            try:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                fh.close()
            except Exception:
                pass

        return OrderFilled(
            symbol=symbol,
            side=side_n,
            qty=float(qty),
            price=float(px),
            fee=float(fee),
            ts=datetime.now(timezone.utc),
        )
