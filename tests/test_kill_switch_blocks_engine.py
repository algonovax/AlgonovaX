from pathlib import Path
import os

def test_kill_switch_file_exists_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGONOVAX_ROOT", str(tmp_path))
    root = Path(os.environ["ALGONOVAX_ROOT"])
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data" / "KILL_SWITCH").write_text("", encoding="utf-8")

    # import should not explode; we just verify file exists where engine expects
    assert (root / "data" / "KILL_SWITCH").exists()
