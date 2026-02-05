from pathlib import Path

def test_killswitch_hard_soft_helper(tmp_path, monkeypatch):
    # simulate repo root in tmpdir
    root = tmp_path / "AlgonovaX"
    data = root / "data"
    data.mkdir(parents=True)

    hard = data / "KILL_SWITCH"
    soft = data / "KILL_SWITCH_SOFT"

    # import function under test
    from algonovax.engine import runtime

    # hard off, soft off
    assert runtime._kill_switch_active_hard_soft(str(hard)) is False

    # soft on should trip even if hard file absent
    soft.write_text("", encoding="utf-8")
    assert runtime._kill_switch_active_hard_soft(str(hard)) is True

    # hard on also trips
    soft.unlink()
    hard.write_text("", encoding="utf-8")
    assert runtime._kill_switch_active_hard_soft(str(hard)) is True
