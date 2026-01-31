from __future__ import annotations

from pathlib import Path
import pytest

from algonovax.config import load_settings


def test_live_requires_kill_switch_off_when_flag_on(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("EXCHANGE", "kraken")
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "1")
    monkeypatch.setenv("KRAKEN_API_KEY", "x")
    monkeypatch.setenv("KRAKEN_API_SECRET", "y")

    monkeypatch.setenv("REQUIRE_KILL_SWITCH_OFF_FOR_LIVE", "1")
    monkeypatch.setenv("KILL_SWITCH_PATH", "./data/KILL_SWITCH")

    # kill switch present => reject
    (tmp_path / "data" / "KILL_SWITCH").write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_settings()

    # kill switch absent => ok
    (tmp_path / "data" / "KILL_SWITCH").unlink(missing_ok=True)
    s = load_settings()
    assert s.live_trading is True
