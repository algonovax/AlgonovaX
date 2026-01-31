import json
from pathlib import Path

from algonovax.config import load_settings
from algonovax.exchanges.paper import PaperExchange


def read_wallet(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def write_wallet(p: Path, quote: float, base: float) -> None:
    p.write_text(json.dumps({"quote": quote, "base": base}, indent=2), encoding="utf-8")


def test_buy_sell_wallet_math(tmp_path, monkeypatch):
    # deterministic env
    monkeypatch.setenv("ALGONOVAX_ROOT", str(tmp_path))
    monkeypatch.setenv("PAPER_WALLET_PATH", str(tmp_path / "paper_wallet.json"))
    monkeypatch.setenv("PAPER_FEE_QUOTE", "0")
    monkeypatch.setenv("PAPER_FEE_RATE", "0.001")  # 0.1%
    monkeypatch.setenv("PAPER_DEFAULT_PRICE", "50000")

    s = load_settings()
    ex = PaperExchange(s)

    wpath = ex.wallet_path
    write_wallet(wpath, quote=1000.0, base=0.0)

    # BUY 0.001 @ 50010
    buy_px = 50010.0
    buy = ex.place_market_order(s.symbol, "buy", 0.001, price_hint=buy_px)

    w1 = read_wallet(wpath)
    assert abs(w1["base"] - 0.001) < 1e-12
    # cost=50.01 fee=0.05001 total=50.06001 quote=949.93999
    assert abs(w1["quote"] - 949.93999) < 1e-9

    # SELL 0.001 @ 50020
    sell_px = 50020.0
    sell = ex.place_market_order(s.symbol, "sell", 0.001, price_hint=sell_px)

    w2 = read_wallet(wpath)
    assert abs(w2["base"] - 0.0) < 1e-12
    # proceeds=50.02 fee=0.05002 net=49.96998 final=999.90997
    assert abs(w2["quote"] - 999.90997) < 1e-9

    # sanity: exchange fees recorded
    assert abs(buy.fee - 0.05001) < 1e-12
    assert abs(sell.fee - 0.05002) < 1e-12
